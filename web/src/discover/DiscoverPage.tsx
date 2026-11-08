import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../api/client'
import type { DiscoverPage as DiscoverPageData, DiscoverSection, MediaType } from '../api/types'
import { useApi } from '../api/useApi'
import { LangLabel } from '../i18n/LangLabel'
import { useLang } from '../i18n/useLang'
import { useIsolating } from '../taste/useIsolating'
import { DiscoverCard } from './DiscoverCard'
import { discoverKeys } from './keys'

const TYPES = ['movie', 'series'] as const satisfies readonly MediaType[]

const BUTTON =
  'min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line'

const chipClass = (pressed: boolean) =>
  `min-h-11 shrink-0 rounded-full border px-4 font-medium ${
    pressed ? 'border-accent bg-accent-soft text-accent' : 'border-line bg-surface text-ink hover:bg-line'
  }`

/** "3 hours ago" in the UI language: the largest of days, hours and minutes that fits. */
function relativeTime(iso: string, lang: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  const format = new Intl.RelativeTimeFormat(lang, { numeric: 'auto' })
  if (minutes >= 24 * 60) return format.format(-Math.round(minutes / (24 * 60)), 'day')
  if (minutes >= 60) return format.format(-Math.round(minutes / 60), 'hour')
  return format.format(-Math.max(minutes, 0), 'minute')
}

/** `/discover`: external titles only (Trending, Top rated, Because you rated), each with its source. */
export function DiscoverPage() {
  const { t } = useTranslation()
  const api = useApi()
  const lang = useLang()
  const [type, setType] = useState<MediaType>('movie')
  const [genre, setGenre] = useState<number | null>(null)

  const query = useQuery({
    queryKey: discoverKeys.page(type, lang, genre),
    queryFn: ({ signal }) =>
      api<DiscoverPageData>(
        `/discover?type=${type}&lang=${lang}${genre === null ? '' : `&genre=${genre}`}`,
        { signal },
      ),
    // Picking a genre keeps the chips (and the old lists, dimmed) on screen until the new list is
    // in; switching Movies/Series does not, since the other type has other genres.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[2] === type ? previous : undefined,
  })
  const page = query.data

  // The chips outlive a failed filtered fetch: remember the last genres seen for this media type,
  // so the user can still clear the genre (a failed query has no data, not even the placeholder).
  const [seen, setSeen] = useState<{ type: MediaType; genres: DiscoverPageData['genres'] } | null>(
    null,
  )
  if (page && (seen?.type !== type || seen.genres !== page.genres)) {
    setSeen({ type, genres: page.genres })
  }
  const genres = page?.genres ?? (seen?.type === type ? seen.genres : [])

  const pickType = (next: MediaType) => {
    if (next === type) return
    setType(next)
    setGenre(null)
  }

  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      <h1 className="text-2xl font-extrabold">{t('nav.discover')}</h1>
      <div className="flex flex-wrap gap-2">
        {TYPES.map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={type === value}
            onClick={() => pickType(value)}
            className={chipClass(type === value)}
          >
            {t(`discover.type.${value}`)}
          </button>
        ))}
      </div>

      {genres.length > 0 && (
        <div className="flex min-w-0 flex-nowrap gap-2 overflow-x-auto pb-1">
          <button
            type="button"
            aria-pressed={genre === null}
            onClick={() => setGenre(null)}
            className={chipClass(genre === null)}
          >
            {t('discover.allGenres')}
          </button>
          {genres.map((g) => (
            <button
              key={g.id}
              type="button"
              aria-pressed={genre === g.id}
              onClick={() => setGenre(genre === g.id ? null : g.id)}
              className={chipClass(genre === g.id)}
            >
              <bdi dir="auto">{g.name}</bdi>
            </button>
          ))}
        </div>
      )}

      {page?.stale && page.fetched_at && (
        <p className="text-sm text-muted">
          {t('discover.updated', { when: relativeTime(page.fetched_at, lang) })}
        </p>
      )}

      {query.isError && !page ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="text-sm font-medium text-danger">
            {query.error instanceof ApiError && query.error.detail === 'discover_unavailable'
              ? t('discover.unavailable')
              : t('common.error')}
          </p>
          <button type="button" onClick={() => void query.refetch()} className={BUTTON}>
            {t('common.retry')}
          </button>
        </div>
      ) : !page ? (
        <p role="status" className="text-muted">
          {t('auth.loading')}
        </p>
      ) : (
        <div
          aria-busy={query.isPlaceholderData}
          className={`flex flex-col gap-6 ${query.isPlaceholderData ? 'opacity-60' : ''}`}
        >
          {page.sections.map((section) => (
            <SectionRow key={sectionId(section)} section={section} />
          ))}
        </div>
      )}
    </section>
  )
}

/** Unique per section: the two `because` sections are told apart by their seed title. */
function sectionId(section: DiscoverSection): string {
  return section.key === 'because' && section.seed
    ? `because-${section.seed.title_id}`
    : section.key
}

function SectionRow({ section }: { section: DiscoverSection }) {
  const { t } = useTranslation()
  const isolating = useIsolating()
  const headingId = `discover-${sectionId(section)}`
  const seed = section.seed
  const heading =
    section.key === 'because' && seed
      ? isolating('discover.section.because', {
          name: { text: seed.name ?? '', dir: 'auto' },
          rating: { text: seed.rating.toFixed(1), dir: 'ltr' },
        })
      : t(`discover.section.${section.key}`)
  return (
    <section aria-labelledby={headingId} className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-col gap-0.5">
        <h2 id={headingId} className="text-lg font-bold text-ink">
          {heading}
        </h2>
        {seed && <LangLabel lang={seed.name_lang} />}
        <p className="text-xs text-muted">{t('discover.fromTmdb')}</p>
      </div>
      <ul className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2">
        {section.items.map((item) => (
          <li key={`${item.media_type}-${item.tmdb_id}`} className="w-32 shrink-0 snap-start">
            <DiscoverCard item={item} />
          </li>
        ))}
      </ul>
    </section>
  )
}
