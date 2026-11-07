import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { OnboardingState } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import {
  fakeApi,
  GENRE_KEYS,
  ONBOARDING_STATE,
  quizTitleRoutes,
  type FakeRoute,
} from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { TasteQuizPage } from './TasteQuizPage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

// Under machine load the default 15 s has timed out; give this heavy file room.
vi.setConfig({ testTimeout: 30_000 })

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

function setup(
  state: OnboardingState = ONBOARDING_STATE,
  extra: Record<string, FakeRoute> = {},
  lang: 'he' | 'en' = 'he',
) {
  const fake = fakeApi({
    'GET /onboarding': state,
    ...quizTitleRoutes(lang),
    'POST /onboarding': { ...state, done: true },
    ...extra,
  })
  const view = renderApp(
    <Routes>
      <Route path="/taste" element={<TasteQuizPage />} />
      <Route path="/" element={<p>HOME</p>} />
    </Routes>,
    { api: fake.api, route: '/taste' },
  )
  return { fake, ...view }
}

const genre = (key: string) =>
  screen.getByRole('button', {
    name: (he.quiz.genre as Record<string, string>)[key],
  })
const done = () => screen.getByRole('button', { name: he.quiz.finish })
const progress = (count: number) => he.quiz.progress.replace('{{count}}', String(count))
const allSliders = async () => {
  await vi.waitFor(() => expect(screen.getAllByRole('slider')).toHaveLength(10))
  return screen.getAllByRole('slider')
}
const progressLine = () =>
  (screen.getByRole('status').textContent ?? '').replace(/\s+/g, ' ').trim()
const posts = (fake: ReturnType<typeof setup>['fake']) =>
  fake.calls.mock.calls.filter(([, init]) => init?.method === 'POST')

async function pick(...keys: string[]) {
  await screen.findByRole('button', { name: he.quiz.genre.action })
  for (const key of keys) await userEvent.click(genre(key))
}

describe('TasteQuizPage', () => {
  it('shows the heading, the private note and all genres', async () => {
    setup()
    expect(await screen.findByRole('heading', { name: he.quiz.title })).toBeInTheDocument()
    expect(screen.getByText(he.quiz.private)).toBeInTheDocument()
    expect(await screen.findByText(he.quiz.genresHint)).toBeInTheDocument()
    for (const key of GENRE_KEYS) expect(genre(key)).toHaveAttribute('aria-pressed', 'false')
  })

  it('prefills the genres picked earlier', async () => {
    const state = {
      ...ONBOARDING_STATE,
      genres: ONBOARDING_STATE.genres.map((g) => ({
        ...g,
        picked: g.key === 'drama',
      })),
    }
    setup(state)
    await screen.findByRole('button', { name: he.quiz.genre.drama })
    expect(genre('drama')).toHaveAttribute('aria-pressed', 'true')
    expect(genre('comedy')).toHaveAttribute('aria-pressed', 'false')
  })

  it('needs 3 to 5 genres before Done', async () => {
    setup()
    await pick('action', 'drama')
    expect(done()).toBeDisabled()
    await userEvent.click(genre('comedy'))
    expect(done()).toBeEnabled()
    await userEvent.click(genre('crime'))
    await userEvent.click(genre('horror'))
    expect(done()).toBeEnabled()
    // Five picked: the rest are refused, the picked ones can still be unpicked.
    expect(genre('war')).toBeDisabled()
    expect(genre('action')).toBeEnabled()
    await userEvent.click(genre('action'))
    expect(genre('action')).toHaveAttribute('aria-pressed', 'false')
    expect(genre('war')).toBeEnabled()
    expect(genre('crime')).toHaveAttribute('aria-pressed', 'true')
  })

  it('sends picks and ratings', async () => {
    const { fake } = setup()
    await pick('action', 'drama', 'comedy')
    const sliders = await screen.findAllByRole('slider')
    expect(sliders).toHaveLength(10)
    expect(progressLine()).toBe(progress(0))
    fireEvent.change(sliders[0], { target: { value: '8.5' } })
    expect(progressLine()).toBe(progress(1))
    await userEvent.click(done())
    await screen.findByText('HOME')
    expect(posts(fake)).toEqual([
      [
        '/onboarding',
        {
          method: 'POST',
          body: {
            genres: ['action', 'comedy', 'drama'],
            ratings: [{ title_id: 1278, rating: 8.5 }],
          },
        },
      ],
    ])
  })

  it('sends only genres when nothing was rated', async () => {
    const { fake } = setup()
    await pick('action', 'drama', 'comedy')
    await userEvent.click(done())
    await screen.findByText('HOME')
    expect(posts(fake)[0][1]).toMatchObject({ body: { ratings: [] } })
  })

  it('refreshes the account, posts, titles and the wishlist after Done', async () => {
    const { client } = setup()
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    await pick('action', 'drama', 'comedy')
    await userEvent.click(done())
    await screen.findByText('HOME')
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey)
    expect(keys).toEqual(expect.arrayContaining([['me'], ['posts'], ['title'], ['wishlist']]))
  })

  it('counts ratings towards 5, then says there are enough', async () => {
    setup()
    await pick('action', 'drama', 'comedy')
    const sliders = await screen.findAllByRole('slider')
    for (const slider of sliders.slice(0, 4)) fireEvent.change(slider, { target: { value: '7' } })
    expect(progressLine()).toBe(progress(4))
    fireEvent.change(sliders[4], { target: { value: '7' } })
    expect(progressLine()).toBe(he.quiz.progressEnough.replace('{{count}}', '5'))
    for (const slider of sliders.slice(5, 7)) fireEvent.change(slider, { target: { value: '7' } })
    expect(progressLine()).toBe('דורגו 7 — מספיק להתאמת טעם')
    // The number is its own left-to-right run inside the right-to-left line.
    expect(within(screen.getByRole('status')).getByText('7').closest('bdi')).not.toBeNull()
  })

  it('counts ratings in English without ever saying 7 of 5', async () => {
    await setLocale('en')
    setup(ONBOARDING_STATE, {}, 'en')
    await screen.findByRole('button', { name: en.quiz.genre.action })
    const sliders = await allSliders()
    for (const slider of sliders.slice(0, 4)) fireEvent.change(slider, { target: { value: '7' } })
    expect(progressLine()).toBe('4 of 5 rated')
    expect(within(screen.getByRole('status')).getByText('4').closest('bdi')).not.toBeNull()
    for (const slider of sliders.slice(4, 7)) fireEvent.change(slider, { target: { value: '7' } })
    expect(progressLine()).toBe('7 rated — enough for Taste Match')
    expect(within(screen.getByRole('status')).getByText('7').closest('bdi')).not.toBeNull()
  })

  it('has the exact progress copy in Hebrew and English', () => {
    expect(he.quiz.progressEnough).toBe('דורגו {{count}} — מספיק להתאמת טעם')
    expect(en.quiz.progressEnough).toBe('{{count}} rated — enough for Taste Match')
  })

  it('names each slider and Not seen button after its title', async () => {
    const routes = quizTitleRoutes('he')
    const key = 'GET /titles/tmdb/movie/278?lang=he'
    setup(ONBOARDING_STATE, { [key]: { ...routes[key], name: 'Inception' } })
    await pick('action', 'drama', 'comedy')
    const slider = await screen.findByRole('slider', {
      name: new RegExp(`${he.compose.rating}.*Inception`),
    })
    const notSeen = screen.getByRole('button', {
      name: `${he.quiz.notSeen} Inception`,
    })
    const row = screen.getByText('Inception').closest('li')!
    expect(row).toContainElement(slider)
    expect(row).toContainElement(notSeen)
    // Each of the ten rows gets its own names.
    expect(
      screen.getAllByRole('button', {
        name: new RegExp(`^${he.quiz.notSeen} `),
      }),
    ).toHaveLength(10)
  })

  it('skips titles not seen and shows existing ratings', async () => {
    const state = {
      ...ONBOARDING_STATE,
      quiz: ONBOARDING_STATE.quiz.map((q, i) => (i === 1 ? { ...q, my_rating: 7 } : q)),
    }
    const { fake } = setup(state)
    await pick('action', 'drama', 'comedy')
    // One title already has a rating: no input for it.
    expect(await screen.findAllByRole('slider')).toHaveLength(9)
    const mine = screen.getByText(he.quiz.yourRating).closest('li')!
    expect(within(mine).getByText('7.0').closest('bdi')).not.toBeNull()
    expect(within(mine).queryByRole('slider')).not.toBeInTheDocument()
    expect(
      within(mine).queryByRole('button', { name: new RegExp(`^${he.quiz.notSeen}`) }),
    ).not.toBeInTheDocument()

    const first = screen.getByText('Quiz 278').closest('li')!
    await userEvent.click(
      within(first).getByRole('button', { name: `${he.quiz.notSeen} Quiz 278` }),
    )
    expect(within(first).queryByRole('slider')).not.toBeInTheDocument()
    expect(screen.getAllByRole('slider')).toHaveLength(8)

    // Only a rating made in this visit is sent (not the existing 7, not the skipped one).
    fireEvent.change(screen.getAllByRole('slider')[0], {
      target: { value: '6' },
    })
    await userEvent.click(done())
    await screen.findByText('HOME')
    expect(posts(fake)[0][1]).toMatchObject({
      body: { ratings: [{ title_id: 28205, rating: 6 }] },
    })
  })

  it('does not send a rating after the title was marked not seen', async () => {
    const { fake } = setup()
    await pick('action', 'drama', 'comedy')
    const sliders = await screen.findAllByRole('slider')
    fireEvent.change(sliders[0], { target: { value: '9' } })
    const first = screen.getByText('Quiz 278').closest('li')!
    await userEvent.click(
      within(first).getByRole('button', { name: `${he.quiz.notSeen} Quiz 278` }),
    )
    expect(progressLine()).toBe(progress(0))
    await userEvent.click(done())
    await screen.findByText('HOME')
    expect(posts(fake)[0][1]).toMatchObject({ body: { ratings: [] } })
  })

  it('Skip for now sends nothing', async () => {
    const { fake } = setup()
    await pick('action')
    await userEvent.click(screen.getByRole('button', { name: he.quiz.skip }))
    await screen.findByText('HOME')
    expect(posts(fake)).toHaveLength(0)
  })

  it('disables Skip for now while the save is pending', async () => {
    let finishSave: () => void = () => {}
    const pending = new Promise<OnboardingState>((resolve) => {
      finishSave = () => resolve(ONBOARDING_STATE)
    })
    setup(ONBOARDING_STATE, { 'POST /onboarding': () => pending })
    await pick('action', 'drama', 'comedy')
    await userEvent.click(done())
    const skip = screen.getByRole('button', { name: he.quiz.skip })
    await vi.waitFor(() => expect(skip).toBeDisabled())
    expect(done()).toBeDisabled()
    finishSave()
    await screen.findByText('HOME')
  })

  it('still refreshes the lists when the page was left while saving', async () => {
    let finishSave: () => void = () => {}
    const pending = new Promise<OnboardingState>((resolve) => {
      finishSave = () => resolve(ONBOARDING_STATE)
    })
    const { client, unmount } = setup(ONBOARDING_STATE, {
      'POST /onboarding': () => pending,
    })
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    await pick('action', 'drama', 'comedy')
    await userEvent.click(done())
    unmount()
    finishSave()
    await vi.waitFor(() => {
      const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey)
      expect(keys).toEqual(expect.arrayContaining([['me'], ['posts'], ['title'], ['wishlist']]))
    })
  })

  it('shows an error and lets you try again when saving fails', async () => {
    let fail = true
    const { fake } = setup(ONBOARDING_STATE, {
      'POST /onboarding': () => {
        if (fail) throw new ApiError(503, 'catalog_unavailable')
        return ONBOARDING_STATE
      },
    })
    await pick('action', 'drama', 'comedy')
    await userEvent.click(done())
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    expect(screen.queryByText('HOME')).not.toBeInTheDocument()
    expect(done()).toBeEnabled()
    fail = false
    await userEvent.click(done())
    await screen.findByText('HOME')
    expect(posts(fake)).toHaveLength(2)
  })

  it('leaves out a title that fails to load', async () => {
    setup(ONBOARDING_STATE, {
      'GET /titles/tmdb/movie/278?lang=he': () => {
        throw new ApiError(500, 'error')
      },
    })
    await vi.waitFor(() => expect(screen.getAllByRole('slider')).toHaveLength(9))
    expect(screen.queryByText('Quiz 278')).not.toBeInTheDocument()
  })

  it('names the language of a title shown in the other language', async () => {
    const routes = quizTitleRoutes('he')
    const key = 'GET /titles/tmdb/movie/278?lang=he'
    setup(ONBOARDING_STATE, { [key]: { ...routes[key], name_lang: 'en' } })
    const row = (await screen.findByText('Quiz 278')).closest('li')!
    expect(within(row).getByText(he.lang.en)).toBeInTheDocument()
  })

  it('shows an error when the quiz cannot be loaded', async () => {
    setup(ONBOARDING_STATE, {
      'GET /onboarding': () => {
        throw new ApiError(500, 'error')
      },
    })
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
  })

  it('works in English', async () => {
    await setLocale('en')
    setup(ONBOARDING_STATE, {}, 'en')
    expect(await screen.findByRole('heading', { name: en.quiz.title })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: en.quiz.genre.scifi })).toBeInTheDocument()
  })
})

describe('genre names', () => {
  it.each([
    ['he', he],
    ['en', en],
  ])('every genre key has a name in %s', (_lang, strings) => {
    for (const key of GENRE_KEYS) {
      expect((strings.quiz.genre as Record<string, string>)[key], key).toEqual(expect.any(String))
    }
    expect(Object.keys(strings.quiz.genre)).toHaveLength(GENRE_KEYS.length)
  })
})
