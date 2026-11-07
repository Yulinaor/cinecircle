import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { PostCard as PostCardData } from '../api/types'
import { LangLabel } from '../i18n/LangLabel'
import { Avatar } from '../people/Avatar'
import { useSeasonName } from './seasonName'

const BADGE = 'rounded-full bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent'

/** The one way a post is shown, on every screen. */
export function PostCard({ post }: { post: PostCardData }) {
  const { t } = useTranslation()
  const seasonName = useSeasonName()
  const { author, title, season } = post
  const isAuthor = author.follow_state === 'self'
  const [revealed, setRevealed] = useState(false)
  const hideOpinion = post.contains_spoilers && !isAuthor && !revealed

  const posterUrl = season?.poster_url ?? title.poster_url
  const seasonLabel = season
    ? seasonName(season.number, season.name, season.name_lang)
    : title.media_type === 'series'
      ? t('post.wholeSeries')
      : null
  // A season post shows the season's summary when it has one, else the title's.
  const summary = season?.overview ? season : title
  const ratings =
    title.imdb_rating !== null
      ? { label: t('post.imdb'), value: title.imdb_rating }
      : title.tmdb_rating !== null
        ? { label: t('post.tmdb'), value: title.tmdb_rating }
        : null

  return (
    <article className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4">
      <header className="flex items-center gap-3">
        <Avatar url={author.avatar_url} name={author.display_name} />
        <Link
          to={`/u/${author.username}`}
          className="flex min-h-11 min-w-0 flex-1 flex-col justify-center"
        >
          <span dir="auto" className="truncate font-semibold text-ink">
            {author.display_name}
          </span>
          <span className="truncate text-sm text-muted">
            <bdi>@{author.username}</bdi>
          </span>
        </Link>
        {!post.is_shared && <span className={BADGE}>{t('post.private')}</span>}
        {post.edited && <span className={BADGE}>{t('post.edited')}</span>}
      </header>

      <div className="flex gap-3">
        {posterUrl ? (
          <img
            src={posterUrl}
            alt=""
            loading="lazy"
            className="aspect-[2/3] w-24 shrink-0 self-start rounded-xl bg-line object-cover"
          />
        ) : (
          <div
            aria-hidden="true"
            data-testid="poster-placeholder"
            className="aspect-[2/3] w-24 shrink-0 self-start rounded-xl bg-line"
          />
        )}
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <h2 className="text-lg font-bold leading-snug text-ink">
            <Link to={`/titles/${title.id}`} dir="auto" className="hover:underline">
              {title.name}
            </Link>
          </h2>
          {seasonLabel && (
            <p dir="auto" className="text-sm font-medium text-muted">
              {seasonLabel}
            </p>
          )}
          <p className="text-ink">
            {/* One left-to-right run, so a right-to-left screen still reads "9.0/10". */}
            <bdi dir="ltr" className="inline-flex items-baseline gap-1">
              <span className="text-3xl font-extrabold">{post.rating.toFixed(1)}</span>
              <span className="text-sm text-muted">{t('post.outOf')}</span>
            </bdi>
          </p>
          <MetaLine post={post} />
          {ratings && (
            <p className="text-sm text-muted">
              {ratings.label} <bdi>{ratings.value.toFixed(1)}</bdi>
            </p>
          )}
        </div>
      </div>

      {post.opinion &&
        (hideOpinion ? (
          <div className="flex flex-wrap items-center gap-3 rounded-xl bg-bg p-3">
            <p className="text-sm text-muted">{t('post.spoiler')}</p>
            <button
              type="button"
              onClick={() => setRevealed(true)}
              className="min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line"
            >
              {t('post.showSpoiler')}
            </button>
          </div>
        ) : (
          <p dir="auto" className="whitespace-pre-wrap break-words text-ink">
            {post.opinion}
          </p>
        ))}

      {summary.overview && (
        <div className="flex flex-col gap-1">
          <LangLabel lang={summary.overview_lang} />
          <p dir="auto" className="line-clamp-3 text-sm text-muted">
            {summary.overview}
          </p>
        </div>
      )}

      {isAuthor && (
        <Link
          to={`/posts/${post.id}/edit`}
          className="inline-flex min-h-11 items-center self-start font-medium text-accent hover:underline"
        >
          {t('post.edit')}
        </Link>
      )}
    </article>
  )
}

/** Year · runtime · genres, skipping what the title doesn't have. */
function MetaLine({ post }: { post: PostCardData }) {
  const { t } = useTranslation()
  const { title } = post
  const parts = [
    title.year_start !== null && <bdi key="year">{title.year_start}</bdi>,
    title.runtime_min !== null && (
      <span key="runtime">{t('post.minutes', { n: title.runtime_min })}</span>
    ),
    title.genres.length > 0 && <span key="genres">{title.genres.join(', ')}</span>,
  ].filter(Boolean)
  if (parts.length === 0) return null
  return (
    <p className="text-sm text-muted">
      {parts.map((part, i) => (
        <span key={i}>
          {i > 0 && ' · '}
          {part}
        </span>
      ))}
    </p>
  )
}
