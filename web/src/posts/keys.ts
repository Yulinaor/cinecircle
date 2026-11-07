import type { Locale } from '../i18n'

/**
 * Query keys for posts and titles. Language is part of every key: the API returns text in the
 * requested language. Every post mutation invalidates `['posts']`, `['title']`, `['profile']`
 * and `['wishlist']`.
 */
export const postKeys = {
  all: ['posts'] as const,
  one: (id: number, lang: Locale) => ['posts', 'one', id, lang] as const,
  feed: (type: string, lang: Locale) => ['posts', 'feed', type, lang] as const,
  user: (username: string, lang: Locale) => ['posts', 'user', username, lang] as const,
}

export const titleKey = (id: number, lang: Locale) => ['title', id, lang] as const
