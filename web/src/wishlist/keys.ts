import type { WishlistStatus } from '../api/types'
import type { Locale } from '../i18n'

/**
 * Query keys for the wishlist. Language is part of every list key: the API returns title text in
 * the requested language. Every wishlist mutation invalidates `['wishlist']`, `['posts']` and
 * `['title']`, since cards and title pages show whether a title is saved.
 */
export const wishlistKeys = {
  all: ['wishlist'] as const,
  list: (status: WishlistStatus, lang: Locale) => ['wishlist', status, lang] as const,
}
