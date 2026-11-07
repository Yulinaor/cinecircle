export type FollowState = 'self' | 'none' | 'requested' | 'following'

export type UserCard = {
  username: string
  display_name: string
  avatar_url: string | null
  follow_state: FollowState
}

export type UserProfile = UserCard & {
  details: {
    bio: string | null
    post_count: number
    /** Owner-only: null when someone else is looking. */
    followers_count: number | null
    following_count: number | null
  } | null
}

export type MyProfile = {
  username: string
  display_name: string
  avatar_url: string | null
  bio: string | null
  locale: 'he' | 'en'
}

export type Me = {
  id: string
  email: string | null
  profile: MyProfile | null
  /** Rated at least one title or picked genres: Taste Match can be shown. */
  taste_unlocked: boolean
}

export type NotificationItem = {
  id: number
  type: 'follow_request' | 'follow_accepted'
  actor: UserCard
  created_at: string
  read: boolean
  request_pending: boolean
}

export type Lang = 'he' | 'en'
export type MediaType = 'movie' | 'series'

/**
 * A personal Taste Match: `fit` is 0-100; `genres` are up to two localised genre names that fit
 * the viewer; `agreement` is the % the viewer agrees with the post's author (posts only).
 */
export type Taste = {
  fit: number
  genres: string[]
  agreement: number | null
}

export type CardTitle = {
  id: number
  media_type: MediaType
  name: string | null
  name_lang: Lang | null
  poster_url: string | null
  year_start: number | null
  runtime_min: number | null
  genres: string[]
  overview: string | null
  overview_lang: Lang | null
  imdb_rating: number | null
  tmdb_rating: number | null
}

export type CardSeason = {
  number: number
  name: string | null
  name_lang: Lang | null
  overview: string | null
  overview_lang: Lang | null
  /** Null when the season has no poster: show the title's. */
  poster_url: string | null
}

export type PostCard = {
  id: number
  author: UserCard
  title: CardTitle
  /** Null for a post on the whole movie / series. */
  season: CardSeason | null
  rating: number
  opinion: string | null
  contains_spoilers: boolean
  is_shared: boolean
  created_at: string
  updated_at: string
  edited: boolean
  /** The viewer's own wishlist holds the title (nobody else's). */
  in_wishlist: boolean
  /** Null on your own posts, or while Taste Match is still locked. */
  taste: Taste | null
}

export type PostPage = {
  posts: PostCard[]
  next_cursor: string | null
}

export type TitleSearchItem = {
  tmdb_id: number
  media_type: MediaType
  name: string
  year: number | null
  poster_url: string | null
}

export type Season = {
  season_number: number
  name: string | null
  name_lang: Lang | null
  overview: string | null
  air_date: string | null
  episode_count: number | null
  poster_url: string | null
}

export type TitleDetail = {
  id: number
  tmdb_id: number
  media_type: MediaType
  imdb_id: string | null
  name: string | null
  name_lang: Lang | null
  overview: string | null
  overview_lang: Lang | null
  year_start: number | null
  year_end: number | null
  runtime_min: number | null
  season_count: number | null
  poster_url: string | null
  genres: { id: number; name: string }[]
  ratings: {
    imdb: { rating: number; votes: number | null } | null
    rotten_tomatoes: number | null
    metacritic: number | null
    tmdb: number | null
  }
  seasons: Season[]
  stale: boolean
  fetched_at: string
}

/** A title with the posts the viewer may see on it, newest first. */
export type TitlePage = TitleDetail & {
  posts: PostCard[]
  in_wishlist: boolean
  taste: Taste | null
}

export type WishlistSort = 'recent' | 'fit'
export type WishlistStatus = 'want' | 'watched'
export type WishlistSource = 'post' | 'discover' | 'search'

/** The post an item was saved from, while the owner can still see it. */
export type WishlistVia = {
  post_id: number
  author: UserCard
}

/** The owner's newest post on the title, any season. */
export type MyPost = {
  id: number
  rating: number
}

export type WishlistItem = {
  title: CardTitle
  status: WishlistStatus
  source: WishlistSource
  via: WishlistVia | null
  added_at: string
  watched_at: string | null
  my_post: MyPost | null
  taste: Taste | null
}

export type WishlistPage = {
  items: WishlistItem[]
  next_cursor: string | null
}
