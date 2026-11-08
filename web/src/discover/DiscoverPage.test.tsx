import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { DiscoverPage as DiscoverPageData } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { DISCOVER_ITEM, DISCOVER_PAGE, fakeApi } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { findPhysicalUtilities } from '../test/rtl'
import { DiscoverPage } from './DiscoverPage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const HE_MOVIES = 'GET /discover?type=movie&lang=he'

function renderDiscover(routes: Parameters<typeof fakeApi>[0]) {
  const fake = fakeApi(routes)
  return { fake, ...renderApp(<DiscoverPage />, { api: fake.api, route: '/discover' }) }
}

describe('DiscoverPage', () => {
  it('shows the sections with source labels', async () => {
    renderDiscover({ [HE_MOVIES]: DISCOVER_PAGE })
    expect(
      await screen.findByRole('heading', { level: 1, name: he.nav.discover }),
    ).toBeInTheDocument()
    const trending = await screen.findByRole('region', { name: he.discover.section.trending })
    const topRated = screen.getByRole('region', { name: he.discover.section.top_rated })
    expect(within(trending).getByText(he.discover.fromTmdb)).toBeInTheDocument()
    expect(within(topRated).getByText(he.discover.fromTmdb)).toBeInTheDocument()

    const cards = within(trending).getAllByRole('link')
    expect(cards).toHaveLength(2)
    // IMDb when present, else TMDB; the source is always named.
    expect(cards[0]).toHaveTextContent('TMDB 7.8')
    expect(cards[1]).toHaveTextContent('IMDb 8.4')
    expect(cards[1]).not.toHaveTextContent('TMDB')
    expect(within(topRated).getByRole('link')).toHaveTextContent('TMDB 8.7')
    for (const card of screen.getAllByRole('link')) {
      expect(card.textContent).toMatch(/(TMDB|IMDb) \d\.\d/)
    }
    expect(cards[0]).toHaveAttribute('href', '/discover/t/movie/603')
    expect(cards[1]).toHaveAttribute('href', '/discover/t/movie/438631')
    expect(within(cards[0]!).getByText('1999')).toBeInTheDocument()
    expect(within(cards[0]!).getByText('המטריקס')).toHaveAttribute('dir', 'auto')
  })

  it('shows Because you rated with the seed', async () => {
    await setLocale('en')
    const page: DiscoverPageData = {
      ...DISCOVER_PAGE,
      sections: [
        ...DISCOVER_PAGE.sections,
        {
          key: 'because',
          seed: { title_id: 5, name: 'Dune', name_lang: 'en', rating: 9 },
          items: [DISCOVER_ITEM],
        },
      ],
    }
    renderDiscover({ 'GET /discover?type=movie&lang=en': page })
    const because = await screen.findByRole('region', { name: 'Because you rated Dune 9.0' })
    const heading = within(because).getByRole('heading')
    expect(heading.textContent).toBe('Because you rated Dune 9.0')
    const isolated = Array.from(heading.querySelectorAll('bdi'))
    expect(isolated.map((el) => el.textContent)).toEqual(['Dune', '9.0'])
    expect(isolated[1]).toHaveAttribute('dir', 'ltr')
    expect(within(because).getByText(en.discover.fromTmdb)).toBeInTheDocument()
  })

  it('names two Because sections apart', async () => {
    await setLocale('en')
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
    const page: DiscoverPageData = {
      ...DISCOVER_PAGE,
      sections: [
        {
          key: 'because',
          seed: { title_id: 5, name: 'The Matrix', name_lang: 'en', rating: 9.5 },
          items: [DISCOVER_ITEM],
        },
        {
          key: 'because',
          seed: { title_id: 6, name: 'Inception', name_lang: 'en', rating: 8.5 },
          items: [DISCOVER_ITEM],
        },
      ],
    }
    renderDiscover({ 'GET /discover?type=movie&lang=en': page })
    const first = await screen.findByRole('region', { name: 'Because you rated The Matrix 9.5' })
    const second = screen.getByRole('region', { name: 'Because you rated Inception 8.5' })
    expect(first).not.toBe(second)
    expect(within(first).getByRole('heading')).toHaveTextContent('The Matrix')
    expect(within(second).getByRole('heading')).toHaveTextContent('Inception')
    expect(errors.mock.calls.flat().join(' ')).not.toMatch(/same key|unique "key"/i)
    errors.mockRestore()
  })

  it('switches to series', async () => {
    const series: DiscoverPageData = {
      ...DISCOVER_PAGE,
      type: 'series',
      sections: [
        {
          key: 'trending',
          seed: null,
          items: [{ ...DISCOVER_ITEM, media_type: 'series', tmdb_id: 1396, name: 'שובר שורות' }],
        },
      ],
    }
    const { fake } = renderDiscover({
      [HE_MOVIES]: DISCOVER_PAGE,
      'GET /discover?type=series&lang=he': series,
    })
    const movies = await screen.findByRole('button', { name: he.discover.type.movie })
    const seriesButton = screen.getByRole('button', { name: he.discover.type.series })
    expect(movies).toHaveAttribute('aria-pressed', 'true')
    expect(seriesButton).toHaveAttribute('aria-pressed', 'false')

    await userEvent.click(seriesButton)
    expect(await screen.findByText('שובר שורות')).toBeInTheDocument()
    expect(fake.count('GET /discover?type=series&lang=he')).toBe(1)
    expect(screen.getByRole('button', { name: he.discover.type.series })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: he.discover.type.movie })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(screen.getByRole('link')).toHaveAttribute('href', '/discover/t/series/1396')
  })

  it('filters by genre and clears', async () => {
    const action: DiscoverPageData = {
      ...DISCOVER_PAGE,
      sections: [{ ...DISCOVER_PAGE.sections[0]!, items: [DISCOVER_ITEM] }],
    }
    const { fake } = renderDiscover({
      [HE_MOVIES]: DISCOVER_PAGE,
      [`${HE_MOVIES}&genre=28`]: action,
      [`${HE_MOVIES}&genre=878`]: action,
    })
    const all = await screen.findByRole('button', { name: he.discover.allGenres })
    expect(all).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'אקשן' })).toHaveAttribute('aria-pressed', 'false')

    await userEvent.click(screen.getByRole('button', { name: 'אקשן' }))
    // The filtered list replaces the full one (no Top rated section); the chips stay.
    await vi.waitFor(() =>
      expect(screen.queryByRole('region', { name: he.discover.section.top_rated })).toBeNull(),
    )
    expect(fake.count(`${HE_MOVIES}&genre=28`)).toBe(1)
    expect(screen.getByRole('button', { name: 'אקשן' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: he.discover.allGenres })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(screen.getByRole('button', { name: 'מדע בדיוני' })).toBeInTheDocument()

    // Pressing the active chip clears the filter.
    await userEvent.click(screen.getByRole('button', { name: 'אקשן' }))
    expect(
      await screen.findByRole('region', { name: he.discover.section.top_rated }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'אקשן' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: he.discover.allGenres })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(fake.log().filter((call) => call.includes('genre='))).toEqual([
      `${HE_MOVIES}&genre=28`,
    ])

    // Picking another chip replaces the first one; "All genres" clears too.
    await userEvent.click(screen.getByRole('button', { name: 'מדע בדיוני' }))
    await vi.waitFor(() => expect(fake.log()).toContain(`${HE_MOVIES}&genre=878`))
    await userEvent.click(screen.getByRole('button', { name: he.discover.allGenres }))
    expect(
      await screen.findByRole('region', { name: he.discover.section.top_rated }),
    ).toBeInTheDocument()
  })

  it('keeps the genre chips when a filtered fetch fails', async () => {
    renderDiscover({
      [HE_MOVIES]: DISCOVER_PAGE,
      [`${HE_MOVIES}&genre=28`]: () => {
        throw new ApiError(503, 'discover_unavailable')
      },
    })
    await userEvent.click(await screen.findByRole('button', { name: 'אקשן' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(he.discover.unavailable)
    // The chips are still there, so the user can clear the genre and recover.
    expect(screen.getByRole('button', { name: 'אקשן' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'מדע בדיוני' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: he.discover.allGenres }))
    expect(
      await screen.findByRole('region', { name: he.discover.section.trending }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does not show old-language chips when a fetch fails after a language switch', async () => {
    const action: DiscoverPageData = {
      ...DISCOVER_PAGE,
      sections: [{ ...DISCOVER_PAGE.sections[0]!, items: [DISCOVER_ITEM] }],
    }
    renderDiscover({
      [HE_MOVIES]: DISCOVER_PAGE,
      [`${HE_MOVIES}&genre=28`]: action,
      'GET /discover?type=movie&lang=en&genre=28': () => {
        throw new ApiError(503, 'discover_unavailable')
      },
    })
    await userEvent.click(await screen.findByRole('button', { name: 'אקשן' }))
    await vi.waitFor(() =>
      expect(screen.queryByRole('region', { name: he.discover.section.top_rated })).toBeNull(),
    )
    await act(() => setLocale('en'))
    expect(await screen.findByRole('alert')).toHaveTextContent(en.discover.unavailable)
    // The remembered chips were Hebrew names; none of them may linger under an English UI.
    expect(screen.queryByRole('button', { name: 'אקשן' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'מדע בדיוני' })).not.toBeInTheDocument()
  })

  it('puts the genre chips in one scrolling row', async () => {
    renderDiscover({ [HE_MOVIES]: DISCOVER_PAGE })
    const all = await screen.findByRole('button', { name: he.discover.allGenres })
    const row = all.parentElement!
    expect(row.className).toContain('overflow-x-auto')
    expect(row.className).toContain('flex-nowrap')
    expect(row.className).not.toContain('flex-wrap')
    for (const chip of Array.from(row.children)) expect(chip.className).toContain('shrink-0')
  })

  it('shows a muted TMDB dash on unrated cards', async () => {
    const page: DiscoverPageData = {
      ...DISCOVER_PAGE,
      sections: [
        {
          key: 'trending',
          seed: null,
          items: [{ ...DISCOVER_ITEM, tmdb_rating: null, imdb_rating: null }],
        },
      ],
    }
    renderDiscover({ [HE_MOVIES]: page })
    const card = await screen.findByRole('link')
    expect(card).toHaveTextContent('TMDB —')
    const dash = within(card).getByText('—', { selector: 'bdi' })
    expect(dash.parentElement).toHaveClass('text-muted')
    // The dash is decoration; screen readers get words.
    expect(dash).toHaveAttribute('aria-hidden', 'true')
    expect(within(card).getByText(he.discover.noRating)).toHaveClass('sr-only')
  })

  it('names the missing rating in the UI language', async () => {
    await setLocale('en')
    const page: DiscoverPageData = {
      ...DISCOVER_PAGE,
      sections: [
        {
          key: 'trending',
          seed: null,
          items: [{ ...DISCOVER_ITEM, tmdb_rating: null, imdb_rating: null }],
        },
      ],
    }
    renderDiscover({ 'GET /discover?type=movie&lang=en': page })
    const card = await screen.findByRole('link')
    expect(within(card).getByText(en.discover.noRating)).toHaveClass('sr-only')
  })

  it('shows the match chip only with taste', async () => {
    const page: DiscoverPageData = {
      ...DISCOVER_PAGE,
      sections: [
        {
          key: 'trending',
          seed: null,
          items: [
            { ...DISCOVER_ITEM, taste: { fit: 76, genres: ['אקשן'], agreement: null } },
            { ...DISCOVER_ITEM, tmdb_id: 2 },
          ],
        },
      ],
    }
    renderDiscover({ [HE_MOVIES]: page })
    const cards = await screen.findAllByRole('link')
    expect(within(cards[0]!).getByTestId('taste-chip')).toHaveTextContent('76')
    expect(within(cards[1]!).queryByTestId('taste-chip')).not.toBeInTheDocument()
  })

  it('labels English names', async () => {
    const page: DiscoverPageData = {
      ...DISCOVER_PAGE,
      sections: [
        {
          key: 'trending',
          seed: null,
          items: [
            { ...DISCOVER_ITEM, name: 'Dune', name_lang: 'en' },
            { ...DISCOVER_ITEM, tmdb_id: 2 },
          ],
        },
      ],
    }
    renderDiscover({ [HE_MOVIES]: page })
    const cards = await screen.findAllByRole('link')
    expect(within(cards[0]!).getByText('Dune')).toHaveAttribute('dir', 'auto')
    expect(within(cards[0]!).getByText(he.lang.en)).toBeInTheDocument()
    expect(within(cards[1]!).queryByText(he.lang.en)).not.toBeInTheDocument()
  })

  it('says when lists are stale', async () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 3_600_000 - 60_000).toISOString()
    await setLocale('en')
    renderDiscover({
      'GET /discover?type=movie&lang=en': { ...DISCOVER_PAGE, stale: true, fetched_at: threeHoursAgo },
    })
    expect(await screen.findByText('Updated 3 hours ago')).toBeInTheDocument()
  })

  it('formats the stale time in Hebrew and stays quiet when fresh', async () => {
    const twoHoursAgo = new Date(Date.now() - 2 * 3_600_000).toISOString()
    const view = renderDiscover({
      [HE_MOVIES]: { ...DISCOVER_PAGE, stale: true, fetched_at: twoHoursAgo },
    })
    const when = new Intl.RelativeTimeFormat('he', { numeric: 'auto' }).format(-2, 'hour')
    expect(await screen.findByText(`עודכן ${when}`)).toBeInTheDocument()
    view.unmount()

    renderDiscover({ [HE_MOVIES]: { ...DISCOVER_PAGE, fetched_at: new Date().toISOString() } })
    await screen.findByRole('region', { name: he.discover.section.trending })
    expect(screen.queryByText(/^עודכן/)).not.toBeInTheDocument()
  })

  it('explains when Discover is unavailable', async () => {
    let fail = true
    renderDiscover({
      [HE_MOVIES]: () => {
        if (fail) throw new ApiError(503, 'discover_unavailable')
        return DISCOVER_PAGE
      },
    })
    expect(await screen.findByRole('alert')).toHaveTextContent(he.discover.unavailable)
    fail = false
    await userEvent.click(screen.getByRole('button', { name: he.common.retry }))
    expect(
      await screen.findByRole('region', { name: he.discover.section.trending }),
    ).toBeInTheDocument()
  })

  it('shows a generic error with retry for other failures', async () => {
    renderDiscover({
      [HE_MOVIES]: () => {
        throw new ApiError(500, 'error')
      },
    })
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(he.common.error)
    expect(alert).not.toHaveTextContent(he.discover.unavailable)
    expect(within(alert).getByRole('button', { name: he.common.retry })).toBeInTheDocument()
  })

  it('fits 390 px', async () => {
    renderDiscover({ [HE_MOVIES]: DISCOVER_PAGE })
    const trending = await screen.findByRole('region', { name: he.discover.section.trending })
    // Rows scroll inside their own container; the page itself does not.
    const row = within(trending).getByRole('list')
    expect(row.className).toContain('overflow-x-auto')
    expect(row.className).toContain('snap-x')
    expect(trending.className).toContain('min-w-0')
    for (const card of screen.getAllByRole('link')) expect(card.className).toContain('min-h-11')
    for (const button of screen.getAllByRole('button')) expect(button.className).toContain('min-h-11')

    const sources = import.meta.glob<string>(['./*.tsx', '!./*.test.tsx'], {
      query: '?raw',
      import: 'default',
      eager: true,
    })
    expect(Object.keys(sources).length).toBeGreaterThanOrEqual(3)
    expect(Object.values(sources).flatMap((source) => findPhysicalUtilities(source))).toEqual([])
  })
})
