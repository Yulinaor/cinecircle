import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Navigate, useParams } from 'react-router'
import { ApiError } from '../api/client'
import type { MediaType, TitleDetail } from '../api/types'
import { useApi } from '../api/useApi'
import { useLang } from '../i18n/useLang'
import { NotFoundPage } from '../pages/NotFoundPage'
import { parsePostId } from '../posts/usePost'
import { discoverKeys } from './keys'

/**
 * `/discover/t/:mediaType/:tmdbId`: caches the TMDB title (`GET /titles/tmdb/...`) and replaces
 * itself with its title page, where Save uses source `discover`. Anything that isn't a movie or
 * series with a positive id is Not found, without a request.
 */
export function DiscoverTitleRedirect() {
  const { mediaType, tmdbId: rawId } = useParams()
  const tmdbId = parsePostId(rawId)
  return (mediaType === 'movie' || mediaType === 'series') && tmdbId !== null ? (
    <Resolve mediaType={mediaType} tmdbId={tmdbId} />
  ) : (
    <NotFoundPage />
  )
}

function Resolve({ mediaType, tmdbId }: { mediaType: MediaType; tmdbId: number }) {
  const { t } = useTranslation()
  const api = useApi()
  const lang = useLang()
  const query = useQuery({
    queryKey: discoverKeys.resolve(mediaType, tmdbId, lang),
    queryFn: ({ signal }) =>
      api<TitleDetail>(`/titles/tmdb/${mediaType}/${tmdbId}?lang=${lang}`, { signal }),
  })
  if (query.data) return <Navigate to={`/titles/${query.data.id}?via=discover`} replace />
  if (query.error instanceof ApiError && query.error.status === 404) return <NotFoundPage />
  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      {query.isError ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="text-sm font-medium text-danger">
            {query.error instanceof ApiError && query.error.detail === 'catalog_unavailable'
              ? t('compose.errors.catalog_unavailable')
              : t('common.error')}
          </p>
          <button
            type="button"
            onClick={() => void query.refetch()}
            className="min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line"
          >
            {t('common.retry')}
          </button>
        </div>
      ) : (
        <p role="status" className="text-muted">
          {t('auth.loading')}
        </p>
      )}
    </section>
  )
}
