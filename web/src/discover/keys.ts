import type { MediaType } from '../api/types'
import type { Locale } from '../i18n'

/**
 * Query keys for Discover. Type, language and genre are part of the page key: the API returns
 * different lists and text for each.
 */
export const discoverKeys = {
  all: ['discover'] as const,
  page: (type: MediaType, lang: Locale, genre: number | null) =>
    ['discover', 'page', type, lang, genre] as const,
  resolve: (mediaType: MediaType, tmdbId: number, lang: Locale) =>
    ['discover', 'resolve', mediaType, tmdbId, lang] as const,
}
