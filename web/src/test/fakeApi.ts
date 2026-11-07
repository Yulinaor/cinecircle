import { vi } from 'vitest'
import { ApiError } from '../api/client'
import type {
  DiscoverItem,
  DiscoverPage,
  ExternalReview,
  MyStats,
  OnboardingState,
  PostCard,
  TitleDetail,
  WishlistItem,
} from '../api/types'
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
  taste: null,
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
  taste: null,
}

/** The 18 genre chip keys, in the order `GET /onboarding` lists them. */
export const GENRE_KEYS = [
  'action',
  'adventure',
  'animation',
  'comedy',
  'crime',
  'documentary',
  'drama',
  'family',
  'fantasy',
  'history',
  'horror',
  'music',
  'mystery',
  'romance',
  'scifi',
  'thriller',
  'war',
  'western',
] as const

const QUIZ_POOL = [
  ['movie', 278],
  ['movie', 155],
  ['movie', 27205],
  ['movie', 597],
  ['movie', 13],
  ['movie', 671],
  ['series', 1668],
  ['series', 1396],
  ['series', 1399],
  ['series', 66732],
] as const

/** A fresh quiz: nothing picked, nothing rated. */
export const ONBOARDING_STATE: OnboardingState = {
  done: false,
  genres: GENRE_KEYS.map((key) => ({ key, picked: false })),
  quiz: QUIZ_POOL.map(([media_type, tmdb_id]) => ({ media_type, tmdb_id, my_rating: null })),
}

/** `GET /titles/tmdb/...` routes for every quiz title; the title id is its TMDB id + 1000. */
export function quizTitleRoutes(lang: 'he' | 'en' = 'he'): Record<string, TitleDetail> {
  return Object.fromEntries(
    QUIZ_POOL.map(([media_type, tmdb_id]) => [
      `GET /titles/tmdb/${media_type}/${tmdb_id}?lang=${lang}`,
      {
        id: tmdb_id + 1000,
        tmdb_id,
        media_type,
        imdb_id: null,
        name: `Quiz ${tmdb_id}`,
        name_lang: lang,
        overview: null,
        overview_lang: null,
        year_start: 1999,
        year_end: null,
        runtime_min: null,
        season_count: null,
        poster_url: null,
        genres: [],
        ratings: { imdb: null, rotten_tomatoes: null, metacritic: null, tmdb: null },
        seasons: [],
        stale: false,
        fetched_at: '2026-11-01T10:00:00+00:00',
      } satisfies TitleDetail,
    ]),
  )
}

/** A TMDB review of a title, 7.5/10, by someone named jdoe; the excerpt contains literal markup. */
export const EXTERNAL_REVIEW: ExternalReview = {
  author_name: 'jdoe',
  excerpt: 'A <b>x</b> film that stays with you.',
  url: 'https://www.themoviedb.org/review/abc',
  author_rating: 7.5,
  source: 'tmdb',
}

/** A TMDB movie in Discover: Hebrew name, TMDB 7.8 only, no Taste Match (still locked). */
export const DISCOVER_ITEM: DiscoverItem = {
  tmdb_id: 603,
  media_type: 'movie',
  name: 'המטריקס',
  name_lang: 'he',
  poster_url: 'https://image.tmdb.org/t/p/w342/matrix.jpg',
  year: 1999,
  genres: [{ id: 28, name: 'אקשן' }],
  tmdb_rating: 7.8,
  imdb_rating: null,
  taste: null,
}

/** A Discover page: Trending (two items) and Top rated (one), fresh, two genre chips. */
export const DISCOVER_PAGE: DiscoverPage = {
  type: 'movie',
  sections: [
    {
      key: 'trending',
      seed: null,
      items: [
        DISCOVER_ITEM,
        { ...DISCOVER_ITEM, tmdb_id: 438631, name: 'דיונה', year: 2021, tmdb_rating: 7.9, imdb_rating: 8.4 },
      ],
    },
    {
      key: 'top_rated',
      seed: null,
      items: [{ ...DISCOVER_ITEM, tmdb_id: 278, name: 'חומות של תקווה', year: 1994, tmdb_rating: 8.7 }],
    },
  ],
  genres: [
    { id: 28, name: 'אקשן' },
    { id: 878, name: 'מדע בדיוני' },
  ],
  stale: false,
  fetched_at: null,
}

/** Twelve rated titles: a spread of ratings, three genres, 9 compared with IMDb (+0.8 on average). */
export const MY_STATS: MyStats = {
  rated: 12,
  distribution: [0, 0, 1, 1, 2, 2, 3, 2, 1, 0].map((count, i) => ({ rating: i + 1, count })),
  genres: [
    { id: 18, name: 'דרמה', count: 3, mean: 7.8 },
    { id: 35, name: 'קומדיה', count: 2, mean: 6.5 },
  ],
  imdb: {
    compared: 9,
    mean_gap: 0.8,
    buckets: [
      { key: 'much_lower', count: 0 },
      { key: 'lower', count: 1 },
      { key: 'same', count: 3 },
      { key: 'higher', count: 4 },
      { key: 'much_higher', count: 1 },
    ],
  },
  agreement: [
    { username: 'gal', display_name: 'Gal', avatar_url: null, agreement: 74, common: 5 },
    { username: 'ron', display_name: 'Ron', avatar_url: null, agreement: 60, common: 3 },
  ],
}

/** A brand-new owner: nothing rated, so every chart is empty. */
export const EMPTY_STATS: MyStats = {
  rated: 0,
  distribution: MY_STATS.distribution.map(({ rating }) => ({ rating, count: 0 })),
  genres: [],
  imdb: {
    compared: 0,
    mean_gap: null,
    buckets: MY_STATS.imdb.buckets.map(({ key }) => ({ key, count: 0 })),
  },
  agreement: [],
}
