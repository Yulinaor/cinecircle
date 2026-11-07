import { vi } from 'vitest'
import { ApiError } from '../api/client'
import type { PostCard, WishlistItem } from '../api/types'
import type { ApiCall } from '../api/useApi'

type Init = { method?: string; body?: unknown } | undefined
export type FakeRoute = unknown | ((init: Init, path: string) => unknown)

/**
 * A fake network keyed by `"METHOD /path"` (query string included). A route is either a value or a
 * function returning one (it may throw an ApiError or return a promise). Unknown routes answer 404.
 */
export function fakeApi(routes: Record<string, FakeRoute>) {
  const fn = vi.fn(async (path: string, init?: Init): Promise<unknown> => {
    const route = routes[`${init?.method ?? 'GET'} ${path}`]
    if (route === undefined) throw new ApiError(404, 'not_found')
    return typeof route === 'function' ? (route as (i: Init, p: string) => unknown)(init, path) : route
  })
  const keyOf = ([path, init]: [string, Init]) => `${init?.method ?? 'GET'} ${path}`
  return {
    api: fn as unknown as ApiCall,
    calls: fn,
    /** `"METHOD /path"` of every call so far, in order. */
    log: () => fn.mock.calls.map((c) => keyOf(c as [string, Init])),
    /** Number of calls to exactly this `"METHOD /path"`. */
    count: (key: string) => fn.mock.calls.filter((c) => keyOf(c as [string, Init]) === key).length,
  }
}

export const DANA = {
  username: 'dana',
  display_name: 'Dana',
  avatar_url: null,
  follow_state: 'none',
} as const

/** A shared 9.0 rating of a movie by Dana, with IMDb 8.4; Hebrew text, no season, not edited. */
export const POST_CARD: PostCard = {
  id: 7,
  author: { ...DANA },
  title: {
    id: 3,
    media_type: 'movie',
    name: 'האודיסאה',
    name_lang: 'he',
    poster_url: 'https://image.tmdb.org/t/p/w342/odyssey.jpg',
    year_start: 2026,
    runtime_min: 150,
    genres: ['דרמה', 'הרפתקאות'],
    overview: 'מסע ארוך הביתה.',
    overview_lang: 'he',
    imdb_rating: 8.4,
    tmdb_rating: 8.0,
  },
  season: null,
  rating: 9,
  opinion: 'סרט מדהים',
  contains_spoilers: false,
  is_shared: true,
  created_at: '2026-11-01T10:00:00+00:00',
  updated_at: '2026-11-01T10:00:00+00:00',
  edited: false,
  in_wishlist: false,
}

/** Dana's post on a movie, saved from that post and still wanted; no rating of your own yet. */
export const WISHLIST_ITEM: WishlistItem = {
  title: POST_CARD.title,
  status: 'want',
  source: 'post',
  via: { post_id: 7, author: { ...DANA } },
  added_at: '2026-11-02T10:00:00+00:00',
  watched_at: null,
  my_post: null,
}
