import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { ApiError } from '../api/client'
import type { Season, TitlePage as TitlePageData } from '../api/types'
import { useApi } from '../api/useApi'
import { LangLabel } from '../i18n/LangLabel'
import { useLang } from '../i18n/useLang'
import { NotFoundPage } from '../pages/NotFoundPage'
import { titleKey } from '../posts/keys'
import { PostCard } from '../posts/PostCard'
import { parsePostId } from '../posts/usePost'
import { ExternalRatings } from './ExternalRatings'

/** `/titles/:id`. A malformed id, or a title the API says is missing, is Not found. */
export function TitlePage() {
  const titleId = parsePostId(useParams().id)
  return titleId === null ? <NotFoundPage /> : <TitlePageBody id={titleId} />
}

function TitlePageBody({ id }: { id: number }) {
  const { t } = useTranslation()
  const api = useApi()
  const lang = useLang()
  const query = useQuery({
    queryKey: titleKey(id, lang),
    queryFn: ({ signal }) => api<TitlePageData>(`/titles/${id}?lang=${lang}`, { signal }),
  })
  if (query.error instanceof ApiError && query.error.status === 404) return <NotFoundPage />
  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      {query.isError ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="text-sm font-medium text-danger">{t('common.error')}</p>
          <button
            type="button"
            onClick={() => void query.refetch()}
            className="min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line"
          >
            {t('common.retry')}
          </button>
        </div>
      ) : !query.data ? (
        <p role="status" className="text-muted">
          {t('auth.loading')}
        </p>
      ) : (
        <TitleBody title={query.data} />
      )}
    </section>
  )
}

function TitleBody({ title }: { title: TitlePageData }) {
  const { t } = useTranslation()
  // A range only when both ends are known and differ; a lone year otherwise.
  const years =
    title.year_start !== null && title.year_end !== null && title.year_end !== title.year_start
      ? `${title.year_start}–${title.year_end}`
      : (title.year_start ?? title.year_end)
  const meta = [
    years !== null && <bdi key="years">{years}</bdi>,
    title.runtime_min !== null && (
      <span key="runtime">{t('post.minutes', { n: title.runtime_min })}</span>
    ),
    title.genres.length > 0 && (
      <span key="genres">{title.genres.map((g) => g.name).join(', ')}</span>
    ),
  ].filter(Boolean)

  return (
    <>
      <div className="flex gap-3">
        {title.poster_url ? (
          <img
            src={title.poster_url}
            alt=""
            className="aspect-[2/3] w-28 shrink-0 self-start rounded-xl bg-line object-cover"
          />
        ) : (
          <div
            aria-hidden="true"
            className="aspect-[2/3] w-28 shrink-0 self-start rounded-xl bg-line"
          />
        )}
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <h1 dir="auto" className="text-2xl font-extrabold leading-snug text-ink">
            {title.name}
          </h1>
          <LangLabel lang={title.name_lang} />
          {meta.length > 0 && (
            <p className="text-sm text-muted">
              {meta.map((part, i) => (
                <span key={i}>
                  {i > 0 && ' · '}
                  {part}
                </span>
              ))}
            </p>
          )}
        </div>
      </div>

      {title.overview && (
        <div className="flex flex-col gap-1">
          <LangLabel lang={title.overview_lang} />
          <p dir="auto" className="whitespace-pre-wrap break-words text-ink">
            {title.overview}
          </p>
        </div>
      )}

      <ExternalRatings ratings={title.ratings} />
      {title.stale && <p className="text-sm text-muted">{t('title.stale')}</p>}

      {title.seasons.length > 0 && <Seasons seasons={title.seasons} />}

      <Link
        to={`/post?title=${title.id}`}
        className="inline-flex min-h-11 items-center justify-center rounded-xl bg-accent px-4 font-semibold text-white hover:opacity-90"
      >
        {t('title.postAbout')}
      </Link>

      {title.posts.length > 0 && (
        <>
          <hr className="border-line" />
          <h2 className="text-lg font-bold text-ink">{t('title.fromPeopleYouFollow')}</h2>
          <div className="flex flex-col gap-4">
            {title.posts.map((post) => (
              <PostCard key={post.id} post={post} />
            ))}
          </div>
        </>
      )}
    </>
  )
}

function Seasons({ seasons }: { seasons: Season[] }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-2">
      <h2 id="title-seasons" className="text-lg font-bold text-ink">
        {t('title.seasons')}
      </h2>
      <ul aria-labelledby="title-seasons" className="flex flex-col divide-y divide-line">
        {seasons.map((season) => (
          <li key={season.season_number} className="flex flex-col gap-0.5 py-2">
            <span dir="auto" className="font-medium text-ink">
              {season.name ?? t('post.season', { n: season.season_number })}
            </span>
            <span className="text-sm text-muted">
              {[
                season.air_date && <bdi key="year">{season.air_date.slice(0, 4)}</bdi>,
                season.episode_count !== null && (
                  <span key="episodes">{t('title.episodes', { n: season.episode_count })}</span>
                ),
              ]
                .filter(Boolean)
                .map((part, i) => (
                  <span key={i}>
                    {i > 0 && ' · '}
                    {part}
                  </span>
                ))}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
