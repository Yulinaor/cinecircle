import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useParams } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { TitleDetail } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { fakeApi, POST_CARD, type FakeRoute } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { AppRoutes } from '../app/routes'
import { ComposePage } from './ComposePage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

// delay: null skips the per-keystroke setTimeout(0), which is slow under parallel load.
const typist = userEvent.setup({ delay: null })

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const DETAIL: TitleDetail = {
  id: 11,
  tmdb_id: 100,
  media_type: 'movie',
  imdb_id: 'tt0100',
  name: 'The Odyssey',
  name_lang: 'he',
  overview: null,
  overview_lang: null,
  year_start: 2026,
  year_end: null,
  runtime_min: 150,
  season_count: null,
  poster_url: null,
  genres: [],
  ratings: { imdb: null, rotten_tomatoes: null, metacritic: null, tmdb: null },
  seasons: [],
  stale: false,
  fetched_at: '2026-11-01T10:00:00+00:00',
}

const season = (n: number, name: string | null, name_lang: 'he' | 'en' | null) => ({
  season_number: n,
  name,
  name_lang,
  overview: null,
  air_date: null,
  episode_count: 9,
  poster_url: null,
})

const SEVERANCE: TitleDetail = {
  ...DETAIL,
  id: 12,
  tmdb_id: 200,
  media_type: 'series',
  name: 'Severance',
  seasons: [
    season(0, 'Specials', 'en'),
    season(1, 'Season 1', 'en'),
    season(2, null, null),
    season(3, 'הפרק האחרון', 'he'),
  ],
}

const SEARCH = (q: string, results: unknown[]) => ({
  [`GET /titles/search?q=${q}&type=all&lang=he`]: { results },
})
const ODYSSEY_HIT = {
  tmdb_id: 100,
  media_type: 'movie',
  name: 'The Odyssey',
  year: 2026,
  poster_url: null,
}
const SEVERANCE_HIT = {
  tmdb_id: 200,
  media_type: 'series',
  name: 'Severance',
  year: 2022,
  poster_url: null,
}

function setup(routes: Record<string, FakeRoute>, route = '/post') {
  const fake = fakeApi({
    ...SEARCH('odyssey', [ODYSSEY_HIT]),
    ...SEARCH('severance', [SEVERANCE_HIT]),
    'GET /titles/tmdb/movie/100?lang=he': DETAIL,
    'GET /titles/tmdb/series/200?lang=he': SEVERANCE,
    'POST /posts': POST_CARD,
    ...routes,
  })
  const view = renderApp(
    <Routes>
      <Route path="/post" element={<ComposePage />} />
      <Route path="/" element={<p>HOME</p>} />
      <Route path="/posts/:id" element={<PostRoute />} />
    </Routes>,
    { api: fake.api, route },
  )
  return { fake, ...view }
}

function PostRoute() {
  return <p>POST {useParams().id}</p>
}

/** The JSON body of the first call to `"METHOD /path"`. */
function bodyOf(fake: ReturnType<typeof setup>['fake'], key: string) {
  const call = fake.calls.mock.calls.find(
    ([path, init]) =>
      `${(init as { method?: string } | undefined)?.method ?? 'GET'} ${path}` === key,
  )
  return (call?.[1] as { body?: unknown } | undefined)?.body
}

async function search(text: string, hit: string) {
  // fireEvent: one change event, no per-keystroke work; the 300 ms debounce still applies.
  fireEvent.change(await screen.findByRole('searchbox', { name: he.compose.search }), {
    target: { value: text },
  })
  await typist.click(await screen.findByRole('button', { name: new RegExp(hit) }))
}

const slider = () => screen.getByRole('slider', { name: he.compose.rating })
const post = () => screen.getByRole('button', { name: he.compose.submit })

describe('ComposePage', () => {
  it('posts with a half-step rating', async () => {
    const { fake } = setup({})
    expect(screen.getByText(he.compose.searchHint)).toBeInTheDocument()
    expect(fake.calls).not.toHaveBeenCalled()

    await search('odyssey', 'The Odyssey')
    expect(await screen.findByRole('heading', { name: 'The Odyssey' })).toBeInTheDocument()
    expect(fake.log()).toContain('GET /titles/tmdb/movie/100?lang=he')
    // A movie has no season picker; Post waits for a rating.
    expect(screen.queryByRole('radiogroup', { name: he.compose.season })).not.toBeInTheDocument()
    expect(post()).toBeDisabled()

    fireEvent.change(slider(), { target: { value: '9' } })
    await typist.type(screen.getByLabelText(he.compose.opinion), '  Epic  ')
    expect(post()).toBeEnabled()
    await typist.click(post())

    expect(await screen.findByText('HOME')).toBeInTheDocument()
    expect(bodyOf(fake, 'POST /posts')).toEqual({
      title_id: 11,
      season_number: 0,
      rating: 9,
      opinion: 'Epic',
      contains_spoilers: false,
      is_shared: true,
    })
  })

  it('sends the spoiler flag and an empty opinion as null', async () => {
    const { fake } = setup({})
    await search('odyssey', 'The Odyssey')
    await typist.click(await screen.findByRole('button', { name: he.compose.increase }))
    await typist.click(screen.getByRole('checkbox', { name: he.compose.spoiler }))
    await typist.type(screen.getByLabelText(he.compose.opinion), '   ')
    await typist.click(post())
    await screen.findByText('HOME')
    expect(bodyOf(fake, 'POST /posts')).toMatchObject({
      rating: 6,
      opinion: null,
      contains_spoilers: true,
    })
  })

  it('series shows the season picker and sends the season', async () => {
    const { fake } = setup({})
    await search('severance', 'Severance')
    const group = await screen.findByRole('radiogroup', { name: he.compose.season })
    const labels = Array.from(group.querySelectorAll('label')).map((l) => l.textContent)
    // Whole series first; TMDB's "Specials" (season 0) would clash with it, so it is not offered.
    // TMDB's name only when it is in the UI language (A6); else the localised "Season N".
    expect(labels).toEqual([he.post.wholeSeries, 'עונה 1', 'עונה 2', 'הפרק האחרון'])
    expect(screen.getByRole('radio', { name: he.post.wholeSeries })).toBeChecked()

    await typist.click(screen.getByRole('radio', { name: 'עונה 1' }))
    fireEvent.change(slider(), { target: { value: '7.5' } })
    await typist.click(post())
    await screen.findByText('HOME')
    expect(bodyOf(fake, 'POST /posts')).toMatchObject({
      title_id: 12,
      season_number: 1,
      rating: 7.5,
    })
  })

  it('keep private sends is_shared false and opens the post, as Home never shows it', async () => {
    const { fake } = setup({ 'POST /posts': { ...POST_CARD, id: 9, is_shared: false } })
    await search('odyssey', 'The Odyssey')
    const visibility = await screen.findByRole('radiogroup', { name: he.compose.visibility })
    expect(within(visibility).getByRole('radio', { name: he.compose.share })).toBeChecked()
    await typist.click(within(visibility).getByRole('radio', { name: he.compose.keepPrivate }))
    fireEvent.change(slider(), { target: { value: '8' } })
    await typist.click(post())
    expect(await screen.findByText('POST 9')).toBeInTheDocument()
    expect(bodyOf(fake, 'POST /posts')).toMatchObject({ is_shared: false })
  })

  it('says so when a search finds nothing', async () => {
    setup(SEARCH('zzz', []))
    fireEvent.change(await screen.findByRole('searchbox', { name: he.compose.search }), {
      target: { value: 'zzz' },
    })
    expect(await screen.findByText(he.compose.noResults)).toBeInTheDocument()
    expect(screen.queryByText(he.auth.loading)).not.toBeInTheDocument()
  })

  it('counts emoji as characters and allows 500', async () => {
    setup({})
    await search('odyssey', 'The Odyssey')
    fireEvent.change(slider(), { target: { value: '8' } })
    const opinion = screen.getByLabelText(he.compose.opinion)
    expect(opinion).not.toHaveAttribute('maxlength')
    expect(opinion).toHaveAttribute('dir', 'auto')

    // "👍🏽" is two code points and four UTF-16 units.
    fireEvent.change(opinion, { target: { value: '👍🏽'.repeat(250) } })
    expect(screen.getByText('500/500')).toBeInTheDocument()
    expect(post()).toBeEnabled()
    const tooLong = he.compose.errors.opinion_too_long.replace('{{max}}', '500')
    expect(screen.queryByText(tooLong)).not.toBeInTheDocument()

    fireEvent.change(opinion, { target: { value: '👍🏽'.repeat(250) + 'a' } })
    expect(screen.getByText('501/500')).toBeInTheDocument()
    expect(post()).toBeDisabled()
    expect(screen.getByText(tooLong)).toBeInTheDocument()
  })

  it('shows Edit your existing post on 409', async () => {
    setup({
      'POST /posts': () => {
        throw new ApiError(409, 'post_exists', { detail: 'post_exists', post_id: 5 })
      },
    })
    await search('odyssey', 'The Odyssey')
    fireEvent.change(slider(), { target: { value: '8' } })
    await typist.click(post())
    expect(await screen.findByRole('alert')).toHaveTextContent(he.compose.errors.post_exists)
    expect(screen.getByRole('link', { name: he.compose.errors.editExisting })).toHaveAttribute(
      'href',
      '/posts/5/edit',
    )
    // Stays on the form, ready to retry.
    expect(post()).toBeEnabled()
  })

  it('explains an invalid season', async () => {
    setup({
      'POST /posts': () => {
        throw new ApiError(422, 'season_invalid', { detail: 'season_invalid' })
      },
    })
    await search('odyssey', 'The Odyssey')
    fireEvent.change(slider(), { target: { value: '8' } })
    await typist.click(post())
    expect(await screen.findByRole('alert')).toHaveTextContent(he.compose.errors.season_invalid)
  })

  it('shows a generic error for any other failure', async () => {
    setup({ 'POST /posts': () => Promise.reject(new ApiError(422, 'error', { detail: [] })) })
    await search('odyssey', 'The Odyssey')
    fireEvent.change(slider(), { target: { value: '8' } })
    await typist.click(post())
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
  })

  it('explains when details cannot load', async () => {
    let fail = true
    const { fake } = setup({
      'GET /titles/tmdb/movie/100?lang=he': () => {
        if (fail) throw new ApiError(503, 'catalog_unavailable')
        return DETAIL
      },
    })
    await search('odyssey', 'The Odyssey')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      he.compose.errors.catalog_unavailable,
    )
    fail = false
    await typist.click(screen.getByRole('button', { name: he.common.retry }))
    expect(await screen.findByRole('heading', { name: 'The Odyssey' })).toBeInTheDocument()
    expect(fake.count('GET /titles/tmdb/movie/100?lang=he')).toBe(2)
  })

  it('preselects a title from ?title=', async () => {
    const { fake } = setup({ 'GET /titles/11?lang=he': { ...DETAIL, posts: [] } }, '/post?title=11')
    expect(await screen.findByRole('heading', { name: 'The Odyssey' })).toBeInTheDocument()
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
    expect(fake.log()).toEqual(['GET /titles/11?lang=he'])

    // Change goes back to the search.
    await typist.click(screen.getByRole('button', { name: he.compose.change }))
    expect(await screen.findByRole('searchbox', { name: he.compose.search })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'The Odyssey' })).not.toBeInTheDocument()
  })

  it('Change returns to the search and forgets the season', async () => {
    const { fake } = setup({})
    await search('severance', 'Severance')
    await typist.click(await screen.findByRole('radio', { name: 'עונה 1' }))
    await typist.click(screen.getByRole('button', { name: he.compose.change }))
    await search('odyssey', 'The Odyssey')
    expect(await screen.findByRole('heading', { name: 'The Odyssey' })).toBeInTheDocument()
    fireEvent.change(slider(), { target: { value: '8' } })
    await typist.click(post())
    await screen.findByText('HOME')
    expect(bodyOf(fake, 'POST /posts')).toMatchObject({ title_id: 11, season_number: 0 })
  })

  it('does not search for blank text', async () => {
    const { fake } = setup({})
    fireEvent.change(await screen.findByRole('searchbox', { name: he.compose.search }), {
      target: { value: '   ' },
    })
    await new Promise((resolve) => setTimeout(resolve, 400))
    expect(fake.calls).not.toHaveBeenCalled()
  })

  it('refreshes posts, titles and profiles after posting', async () => {
    const { client } = setup({})
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    await search('odyssey', 'The Odyssey')
    fireEvent.change(slider(), { target: { value: '8' } })
    await typist.click(post())
    await screen.findByText('HOME')
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey)
    expect(keys).toEqual(expect.arrayContaining([['posts'], ['title'], ['profile']]))
  })
})

describe('routes', () => {
  it('serves the composer at /post and the editor at /posts/:id/edit', async () => {
    const mine = { ...POST_CARD, id: 5, author: { ...POST_CARD.author, follow_state: 'self' } }
    const fake = fakeApi({ 'GET /posts/5?lang=he': mine })
    const first = renderApp(<AppRoutes />, { api: fake.api, route: '/post' })
    expect(screen.getByRole('heading', { name: he.compose.title })).toBeInTheDocument()
    first.unmount()
    renderApp(<AppRoutes />, { api: fake.api, route: '/posts/5/edit' })
    expect(await screen.findByRole('button', { name: he.compose.save })).toBeInTheDocument()
  })
})
