import { Link } from 'react-router'
import type { DiscoverItem } from '../api/types'
import { LangLabel } from '../i18n/LangLabel'
import { TasteChip } from '../taste/TasteLine'

/**
 * One external title in a Discover row; the whole card links to the resolver, which caches the
 * title and lands on its page. Its rating names its source (R4.2): IMDb when we have it, else TMDB.
 */
export function DiscoverCard({ item }: { item: DiscoverItem }) {
  const rating =
    item.imdb_rating !== null
      ? { source: 'IMDb', value: item.imdb_rating }
      : item.tmdb_rating !== null
        ? { source: 'TMDB', value: item.tmdb_rating }
        : null
  return (
    <Link
      to={`/discover/t/${item.media_type}/${item.tmdb_id}`}
      className="flex min-h-11 w-full flex-col gap-1 rounded-xl text-ink hover:opacity-90"
    >
      {item.poster_url ? (
        <img
          src={item.poster_url}
          alt=""
          loading="lazy"
          className="aspect-[2/3] w-full rounded-xl bg-line object-cover"
        />
      ) : (
        <span aria-hidden="true" className="aspect-[2/3] w-full rounded-xl bg-line" />
      )}
      <span dir="auto" className="line-clamp-2 break-words text-sm font-semibold leading-snug">
        {item.name ?? '—'}
      </span>
      <LangLabel lang={item.name_lang} />
      {item.year !== null && (
        <span className="text-xs text-muted">
          <bdi>{item.year}</bdi>
        </span>
      )}
      {rating && (
        <span className="text-xs">
          <span className="text-muted">{rating.source}</span>{' '}
          <bdi className="font-bold">{rating.value.toFixed(1)}</bdi>
        </span>
      )}
      {item.taste && (
        <span className="self-start">
          <TasteChip fit={item.taste.fit} />
        </span>
      )}
    </Link>
  )
}
