import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { TitleDetail, WishlistItem, WishlistPage as WishlistPageData } from '../api/types'
import { AppRoutes } from '../app/routes'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { fakeApi, WISHLIST_ITEM, type FakeRoute } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { WishlistPage } from './WishlistPage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

// delay: null skips the per-keystroke setTimeout(0), which is slow under parallel load.
const typist = userEvent.setup({ delay: null })

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const WANT = 'GET /wishlist?status=want&lang=he'
const WATCHED = 'GET /wishlist?status=watched&lang=he'

const GAL = { username: 'gal', display_name: 'Gal', avatar_url: null, follow_state: 'following' } as const

/** Saved from Gal's post (post 7) on title 3. */
const FROM_GAL: WishlistItem = { ...WISHLIST_ITEM, via: { post_id: 7, author: { ...GAL } } }

/** Saved from search; title 4 is an English-text series with no poster. */
const FROM_SEARCH: WishlistItem = {
  ...WISHLIST_ITEM,
  title: {
    ...WISHLIST_ITEM.title,
    id: 4,
    media_type: 'series',
    name: 'Severance',
    name_lang: 'en',
    poster_url: null,
    year_start: 2022,
  },
  source: 'search',
  via: null,
  added_at: '2026-11-01T10:00:00+00:00',
}

const page = (items: WishlistItem[], next_cursor: string | null = null): WishlistPageData => ({
  items,
  next_cursor,
})

const watched = (item: WishlistItem, my_post: WishlistItem['my_post'] = null): WishlistItem => ({
  ...item,
  status: 'watched',
  watched_at: '2026-11-05T10:00:00+00:00',
  my_post,
})

function setup(routes: Record<string, FakeRoute>) {
  const fake = fakeApi({ [WANT]: page([FROM_GAL, FROM_SEARCH]), ...routes })
  const view = renderApp(<WishlistPage />, { api: fake.api })
  return { fake, ...view }
}

const bodyOf = (fake: ReturnType<typeof setup>['fake'], key: string) => {
  const call = fake.calls.mock.calls.find(
    ([path, init]) =>
      `${(init as { method?: string } | undefined)?.method ?? 'GET'} ${path}` === key,
  )
  return (call?.[1] as { body?: unknown } | undefined)?.body
}

const rowOf = (name: string) =>
  screen.getByRole('link', { name }).closest('li') as HTMLElement

describe('WishlistPage', () => {
  it('has the exact copy in Hebrew and English', () => {
    const pick = (s: typeof he) => [
      s.wishlist.privateNote,
      s.wishlist.tab.want,
      s.wishlist.tab.watched,
      s.wishlist.add,
      s.wishlist.cancel,
      s.wishlist.markWatched,
      s.wishlist.backToWant,
      s.wishlist.remove,
      s.wishlist.rateNow,
      s.wishlist.yourRating,
      s.wishlist.via,
      s.wishlist.from.post,
      s.wishlist.from.discover,
      s.wishlist.from.search,
      s.wishlist.empty.want,
      s.wishlist.empty.watched,
    ]
    expect(pick(he)).toEqual([
      'הרשימה הזו גלויה רק לך.',
      'רוצה לראות',
      'ראיתי',
      'הוספת כותר',
      'ביטול',
      'סימון כנצפה',
      'החזרה ל״רוצה לראות״',
      'הסרה',
      'לדרג עכשיו',
      'הדירוג שלך',
      'דרך {{name}}',
      'מפוסט',
      'מ״גלו״',
      'מהחיפוש',
      'עדיין אין כאן כלום. שמרו כותרים מהבית, מדף כותר או מהחיפוש.',
      'עדיין לא סומנו כותרים כנצפים.',
    ])
    expect(pick(en as unknown as typeof he)).toEqual([
      'Only you can see your wishlist.',
      'Want to watch',
      'Watched',
      'Add a title',
      'Cancel',
      'Mark watched',
      'Move back to Want',
      'Remove',
      'Rate it now',
      'Your rating',
      'via {{name}}',
      'From a post',
      'From Discover',
      'From search',
      'Nothing here yet. Save titles from Home, a title page or search.',
      'Nothing marked watched yet.',
    ])
  })

  it('lists Want items newest first with their source', async () => {
    const { fake } = setup({})
    expect(screen.getByRole('heading', { level: 1, name: he.nav.wishlist })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'האודיסאה' })).toHaveAttribute('href', '/titles/3')
    expect(fake.log()).toEqual([WANT])

    const titles = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(titles).toEqual(['האודיסאה', 'Severance'])

    // Saved from Gal's post: the source line links to that post.
    const gal = rowOf('האודיסאה')
    expect(within(gal).getByRole('link', { name: 'דרך Gal' })).toHaveAttribute('href', '/posts/7')
    // Saved from search: plain text, no link.
    const search = rowOf('Severance')
    expect(within(search).getByText(he.wishlist.from.search)).toBeInTheDocument()
    expect(within(search).queryByRole('link', { name: he.wishlist.from.search })).toBeNull()
    // A series says so; an English name on a Hebrew screen is labelled.
    const meta = within(search).getByText(he.compose.series, { exact: false })
    // Only the number is isolated left-to-right; the separator stays in the line's own direction.
    expect(meta).toHaveTextContent(`2022 · ${he.compose.series}`)
    expect(meta.querySelector('bdi')).toHaveTextContent(/^2022$/)
    expect(within(search).getByText(he.lang.en)).toBeInTheDocument()
    expect(within(gal).queryByText(he.lang.he)).toBeNull()
  })

  it('says "From a post" when the source post is no longer visible', async () => {
    setup({ [WANT]: page([{ ...WISHLIST_ITEM, via: null }]) })
    expect(await screen.findByText(he.wishlist.from.post)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Dana/ })).toBeNull()
  })

  it('names the Discover source', async () => {
    setup({ [WANT]: page([{ ...FROM_SEARCH, source: 'discover' }]) })
    expect(await screen.findByText(he.wishlist.from.discover)).toBeInTheDocument()
  })

  it('shows the private note and the empty state', async () => {
    setup({ [WANT]: page([]) })
    expect(screen.getByText(he.wishlist.privateNote)).toBeInTheDocument()
    expect(await screen.findByText(he.wishlist.empty.want)).toBeInTheDocument()

    await typist.click(screen.getByRole('button', { name: he.wishlist.tab.watched }))
    // The note is not tied to a tab.
    expect(screen.getByText(he.wishlist.privateNote)).toBeInTheDocument()
  })

  it('shows the Watched empty state', async () => {
    setup({ [WATCHED]: page([]) })
    await typist.click(await screen.findByRole('button', { name: he.wishlist.tab.watched }))
    expect(await screen.findByText(he.wishlist.empty.watched)).toBeInTheDocument()
  })

  it('shows loading, then an error with a retry', async () => {
    let fail = true
    const { fake } = setup({
      [WANT]: () => {
        if (fail) throw new ApiError(503, 'db_unavailable')
        return page([FROM_SEARCH])
      },
    })
    expect(screen.getByRole('status')).toHaveTextContent(he.auth.loading)
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    fail = false
    await typist.click(screen.getByRole('button', { name: he.common.retry }))
    expect(await screen.findByRole('link', { name: 'Severance' })).toBeInTheDocument()
    expect(fake.count(WANT)).toBe(2)
  })

  it('switches to Watched', async () => {
    const { fake } = setup({ [WATCHED]: page([watched(FROM_SEARCH)]) })
    const wantTab = screen.getByRole('button', { name: he.wishlist.tab.want })
    const watchedTab = screen.getByRole('button', { name: he.wishlist.tab.watched })
    expect(wantTab).toHaveAttribute('aria-pressed', 'true')
    expect(watchedTab).toHaveAttribute('aria-pressed', 'false')
    await screen.findByRole('link', { name: 'האודיסאה' })

    await typist.click(watchedTab)
    expect(await screen.findByRole('link', { name: 'Severance' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'האודיסאה' })).toBeNull()
    expect(fake.log()).toContain(WATCHED)
    expect(watchedTab).toHaveAttribute('aria-pressed', 'true')
    expect(wantTab).toHaveAttribute('aria-pressed', 'false')
  })

  it('marks an item watched', async () => {
    let marked = false
    const { fake } = setup({
      [WANT]: () => page(marked ? [FROM_SEARCH] : [FROM_GAL, FROM_SEARCH]),
      'PATCH /wishlist/3': () => {
        marked = true
        return watched(FROM_GAL)
      },
    })
    // Named per row: two Mark watched buttons, told apart by their title.
    const button = await screen.findByRole('button', { name: `${he.wishlist.markWatched} האודיסאה` })
    expect(screen.getByRole('button', { name: `${he.wishlist.markWatched} Severance` })).toBeInTheDocument()
    await typist.click(button)

    expect(bodyOf(fake, 'PATCH /wishlist/3')).toEqual({ status: 'watched' })
    await vi.waitFor(() => expect(screen.queryByRole('link', { name: 'האודיסאה' })).toBeNull())
    expect(fake.count(WANT)).toBe(2)
  })

  it('shows an error on the row when an action fails', async () => {
    setup({
      'PATCH /wishlist/3': () => {
        throw new ApiError(503, 'db_unavailable')
      },
    })
    await typist.click(await screen.findByRole('button', { name: `${he.wishlist.markWatched} האודיסאה` }))
    expect(await within(rowOf('האודיסאה')).findByRole('alert')).toHaveTextContent(he.common.error)
    expect(within(rowOf('Severance')).queryByRole('alert')).toBeNull()
  })

  it('offers Rate it now, or shows your rating', async () => {
    const rated = watched(FROM_SEARCH, { id: 12, rating: 8.5 })
    setup({ [WATCHED]: page([watched(FROM_GAL), rated]) })
    await typist.click(screen.getByRole('button', { name: he.wishlist.tab.watched }))
    await screen.findByRole('link', { name: 'Severance' })

    // No post of your own yet: go and rate it.
    const rate = within(rowOf('האודיסאה')).getByRole('link', {
      name: `${he.wishlist.rateNow} האודיסאה`,
    })
    expect(rate).toHaveAttribute('href', '/post?title=3')
    expect(within(rowOf('האודיסאה')).queryByText(he.wishlist.yourRating)).toBeNull()

    // A post of your own: its rating, one left-to-right run, linking to it.
    const mine = within(rowOf('Severance')).getByRole('link', {
      name: `${he.wishlist.yourRating} 8.5 Severance`,
    })
    expect(mine).toHaveAttribute('href', '/posts/12')
    expect(within(mine).getByText('8.5').closest('bdi')).toHaveAttribute('dir', 'ltr')
    expect(within(rowOf('Severance')).queryByRole('link', { name: /Rate it now|לדרג/ })).toBeNull()
  })

  it('moves back to Want and removes', async () => {
    const { fake } = setup({
      [WATCHED]: page([watched(FROM_GAL)]),
      'PATCH /wishlist/3': FROM_GAL,
      'DELETE /wishlist/3': null,
    })
    await typist.click(screen.getByRole('button', { name: he.wishlist.tab.watched }))
    // Watched rows have no Mark watched.
    await screen.findByRole('link', { name: 'האודיסאה' })
    expect(screen.queryByRole('button', { name: new RegExp(he.wishlist.markWatched) })).toBeNull()

    await typist.click(screen.getByRole('button', { name: `${he.wishlist.backToWant} האודיסאה` }))
    expect(bodyOf(fake, 'PATCH /wishlist/3')).toEqual({ status: 'want' })

    await typist.click(screen.getByRole('button', { name: `${he.wishlist.remove} האודיסאה` }))
    expect(fake.count('DELETE /wishlist/3')).toBe(1)
  })

  it('removes a Want item', async () => {
    const { fake } = setup({ 'DELETE /wishlist/4': null })
    await typist.click(await screen.findByRole('button', { name: `${he.wishlist.remove} Severance` }))
    expect(fake.count('DELETE /wishlist/4')).toBe(1)
  })

  it('loads more with the cursor', async () => {
    const { fake } = setup({
      [WANT]: page([FROM_GAL], 'a=|b'),
      [`${WANT}&cursor=a%3D%7Cb`]: page([FROM_SEARCH]),
    })
    await typist.click(await screen.findByRole('button', { name: he.common.loadMore }))
    expect(await screen.findByRole('link', { name: 'Severance' })).toBeInTheDocument()
    // Both pages stay; no more pages, no button.
    expect(screen.getByRole('link', { name: 'האודיסאה' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: he.common.loadMore })).toBeNull()
    expect(fake.log()).toEqual([WANT, `${WANT}&cursor=a%3D%7Cb`])
  })

  it('keeps what loaded when Load more fails, and retries that page', async () => {
    let fail = true
    setup({
      [WANT]: page([FROM_GAL], 'c1'),
      [`${WANT}&cursor=c1`]: () => {
        if (fail) throw new ApiError(503, 'db_unavailable')
        return page([FROM_SEARCH])
      },
    })
    await typist.click(await screen.findByRole('button', { name: he.common.loadMore }))
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    expect(screen.getByRole('link', { name: 'האודיסאה' })).toBeInTheDocument()
    fail = false
    await typist.click(screen.getByRole('button', { name: he.common.retry }))
    expect(await screen.findByRole('link', { name: 'Severance' })).toBeInTheDocument()
  })
})

describe('AddToWishlist', () => {
  const ODYSSEY_HIT = {
    tmdb_id: 100,
    media_type: 'movie',
    name: 'The Odyssey',
    year: 2026,
    poster_url: null,
  }
  const DETAIL: TitleDetail = {
    id: 11,
    tmdb_id: 100,
    media_type: 'movie',
    imdb_id: 'tt0100',
    name: 'The Odyssey',
    name_lang: 'en',
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
  const DETAIL_PATH = 'GET /titles/tmdb/movie/100?lang=he'

  const searchBox = () => screen.findByRole('searchbox', { name: he.compose.search })
  async function openAndPick() {
    await typist.click(await screen.findByRole('button', { name: he.wishlist.add }))
    fireEvent.change(await searchBox(), { target: { value: 'odyssey' } })
    await typist.click(await screen.findByRole('button', { name: /The Odyssey/ }))
  }

  it('adds a title from search', async () => {
    let saved = false
    const { fake } = setup({
      'GET /titles/search?q=odyssey&type=all&lang=he': { results: [ODYSSEY_HIT] },
      [DETAIL_PATH]: DETAIL,
      'POST /wishlist': () => {
        saved = true
        return { ...FROM_SEARCH, title: { ...FROM_SEARCH.title, id: 11 } }
      },
      [WANT]: () => page(saved ? [FROM_SEARCH] : []),
    })
    await openAndPick()

    // The picker closes once it is saved, and the list is refetched.
    await vi.waitFor(() => expect(screen.queryByRole('searchbox')).toBeNull())
    expect(fake.log()).toContain(DETAIL_PATH)
    expect(bodyOf(fake, 'POST /wishlist')).toEqual({ title_id: 11, source: 'search' })
    expect(await screen.findByRole('link', { name: 'Severance' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: he.wishlist.add })).toBeInTheDocument()
  })

  it('switches to Want after adding from the Watched tab', async () => {
    const { fake } = setup({
      'GET /titles/search?q=odyssey&type=all&lang=he': { results: [ODYSSEY_HIT] },
      [DETAIL_PATH]: DETAIL,
      'POST /wishlist': FROM_SEARCH,
      [WATCHED]: page([]),
    })
    await typist.click(await screen.findByRole('button', { name: he.wishlist.tab.watched }))
    await openAndPick()
    await vi.waitFor(() =>
      expect(screen.getByRole('button', { name: he.wishlist.tab.want })).toHaveAttribute(
        'aria-pressed',
        'true',
      ),
    )
    expect(fake.count('POST /wishlist')).toBe(1)
  })

  it('switches to the tab of an item that was already on the list', async () => {
    setup({
      'GET /titles/search?q=odyssey&type=all&lang=he': { results: [ODYSSEY_HIT] },
      [DETAIL_PATH]: DETAIL,
      // Saving is idempotent: the existing item comes back, already watched.
      'POST /wishlist': watched(FROM_SEARCH),
      [WATCHED]: page([watched(FROM_SEARCH)]),
    })
    await openAndPick()
    await vi.waitFor(() =>
      expect(screen.getByRole('button', { name: he.wishlist.tab.watched })).toHaveAttribute(
        'aria-pressed',
        'true',
      ),
    )
    expect(await screen.findByRole('link', { name: 'Severance' })).toBeInTheDocument()
  })

  it('says the catalog is unavailable on 503 and retries', async () => {
    let attempts = 0
    const { fake } = setup({
      'GET /titles/search?q=odyssey&type=all&lang=he': { results: [ODYSSEY_HIT] },
      [DETAIL_PATH]: () => {
        attempts += 1
        if (attempts === 1) throw new ApiError(503, 'catalog_unavailable')
        return DETAIL
      },
      'POST /wishlist': FROM_SEARCH,
    })
    await openAndPick()
    expect(await screen.findByRole('alert')).toHaveTextContent(he.compose.errors.catalog_unavailable)
    expect(fake.count('POST /wishlist')).toBe(0)

    await typist.click(screen.getByRole('button', { name: he.common.retry }))
    await vi.waitFor(() => expect(fake.count('POST /wishlist')).toBe(1))
    expect(bodyOf(fake, 'POST /wishlist')).toEqual({ title_id: 11, source: 'search' })
  })

  it('shows a generic error when saving fails and Cancel closes the picker', async () => {
    const { fake } = setup({
      'GET /titles/search?q=odyssey&type=all&lang=he': { results: [ODYSSEY_HIT] },
      [DETAIL_PATH]: DETAIL,
      'POST /wishlist': () => {
        throw new ApiError(500, 'internal')
      },
    })
    await openAndPick()
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    await typist.click(screen.getByRole('button', { name: he.wishlist.cancel }))
    expect(screen.queryByRole('searchbox')).toBeNull()
    expect(screen.getByRole('button', { name: he.wishlist.add })).toBeInTheDocument()
    expect(fake.count('POST /wishlist')).toBe(1)
  })

  it('Cancel closes the picker without searching', async () => {
    const { fake } = setup({})
    await typist.click(await screen.findByRole('button', { name: he.wishlist.add }))
    expect(await searchBox()).toBeInTheDocument()
    await typist.click(screen.getByRole('button', { name: he.wishlist.cancel }))
    expect(screen.queryByRole('searchbox')).toBeNull()
    expect(fake.log()).toEqual([WANT])
  })
})

describe('routes', () => {
  it('serves the Wishlist screen at /wishlist', async () => {
    const fake = fakeApi({ [WANT]: page([FROM_SEARCH]) })
    renderApp(<AppRoutes />, { api: fake.api, route: '/wishlist' })
    expect(await screen.findByRole('link', { name: 'Severance' })).toBeInTheDocument()
    expect(screen.getByText(he.wishlist.privateNote)).toBeInTheDocument()
  })
})
