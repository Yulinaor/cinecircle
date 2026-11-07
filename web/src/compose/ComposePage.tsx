import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { ApiError } from '../api/client'
import type { TitleDetail, TitleSearchItem } from '../api/types'
import { useApi } from '../api/useApi'
import { useLang } from '../i18n/useLang'
import { NotFoundPage } from '../pages/NotFoundPage'
import { titleKey } from '../posts/keys'
import { parsePostId } from '../posts/usePost'
import { PostForm, type PostFormValues } from './PostForm'
import { SeasonPicker } from './SeasonPicker'
import { TitlePicker } from './TitlePicker'
import { usePostMutations } from './usePostMutations'

const SECONDARY =
  'min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line'

/** `/post`: pick a title (or arrive with `?title=<id>`), then rate it and post. */
export function ComposePage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const presetId = parsePostId(params.get('title') ?? undefined)
  const [picked, setPicked] = useState<TitleSearchItem | null>(null)
  const hasTitle = picked !== null || presetId !== null

  function change() {
    setPicked(null)
    if (presetId !== null) setParams({}, { replace: true })
  }

  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      <h1 className="text-2xl font-extrabold">{t('compose.title')}</h1>
      {hasTitle ? (
        <TitleStep
          // A different title starts a fresh form (rating, opinion, season).
          key={picked ? `${picked.media_type}-${picked.tmdb_id}` : presetId}
          picked={picked}
          presetId={presetId}
          onChange={change}
        />
      ) : (
        <TitlePicker onPick={setPicked} />
      )}
    </section>
  )
}

/** Loads the chosen title's details, then shows the post form for it. */
function TitleStep({
  picked,
  presetId,
  onChange,
}: {
  picked: TitleSearchItem | null
  presetId: number | null
  onChange: () => void
}) {
  const { t } = useTranslation()
  const api = useApi()
  const lang = useLang()
  const path = picked
    ? `/titles/tmdb/${picked.media_type}/${picked.tmdb_id}?lang=${lang}`
    : `/titles/${presetId}?lang=${lang}`
  const detail = useQuery({
    queryKey: picked
      ? ['title', 'tmdb', picked.media_type, picked.tmdb_id, lang]
      : titleKey(presetId ?? 0, lang),
    // The retry button is the retry: show the failure at once.
    retry: false,
    queryFn: ({ signal }) => api<TitleDetail>(path, { signal }),
  })

  if (detail.error instanceof ApiError && detail.error.status === 404) return <NotFoundPage />
  if (detail.isError) {
    return (
      <div role="alert" className="flex flex-col items-start gap-3">
        <p className="text-sm font-medium text-danger">
          {detail.error instanceof ApiError && detail.error.detail === 'catalog_unavailable'
            ? t('compose.errors.catalog_unavailable')
            : t('common.error')}
        </p>
        <div className="flex gap-2">
          <button type="button" onClick={() => void detail.refetch()} className={SECONDARY}>
            {t('common.retry')}
          </button>
          <button type="button" onClick={onChange} className={SECONDARY}>
            {t('compose.change')}
          </button>
        </div>
      </div>
    )
  }
  if (!detail.data) {
    return (
      <p role="status" className="text-muted">
        {t('auth.loading')}
      </p>
    )
  }
  return <ComposeForm title={detail.data} onChange={onChange} />
}

function ComposeForm({ title, onChange }: { title: TitleDetail; onChange: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { create } = usePostMutations()
  const [season, setSeason] = useState(0)
  const hasSeasons = title.media_type === 'series' && title.seasons.some((s) => s.season_number > 0)

  function submit(values: PostFormValues) {
    create.mutate(
      { title_id: title.id, season_number: season, ...values },
      // A private post never shows on Home, so open the post itself.
      { onSuccess: (card) => void navigate(card.is_shared ? '/' : `/posts/${card.id}`) },
    )
  }

  return (
    <>
      <header className="flex items-center gap-3">
        {title.poster_url ? (
          <img
            src={title.poster_url}
            alt=""
            className="aspect-[2/3] w-16 shrink-0 rounded-xl bg-line object-cover"
          />
        ) : (
          <div aria-hidden="true" className="aspect-[2/3] w-16 shrink-0 rounded-xl bg-line" />
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <h2 dir="auto" className="text-lg font-bold leading-snug text-ink">
            {title.name}
          </h2>
          <p className="text-sm text-muted">
            {title.year_start !== null && <bdi>{title.year_start} · </bdi>}
            {t(title.media_type === 'movie' ? 'compose.movie' : 'compose.series')}
          </p>
        </div>
        <button type="button" onClick={onChange} className={SECONDARY}>
          {t('compose.change')}
        </button>
      </header>
      {hasSeasons && <SeasonPicker seasons={title.seasons} value={season} onChange={setSeason} />}
      <PostForm
        onSubmit={submit}
        submitLabel={t('compose.submit')}
        busy={create.isPending}
        error={create.isError ? <CreateError error={create.error} /> : null}
      />
    </>
  )
}

function CreateError({ error }: { error: Error }) {
  const { t } = useTranslation()
  if (error instanceof ApiError) {
    if (error.status === 409 && error.detail === 'post_exists') {
      const body = error.body as { post_id?: unknown } | null
      const postId = typeof body?.post_id === 'number' ? body.post_id : null
      return (
        <p>
          {t('compose.errors.post_exists')}
          {postId !== null && (
            <>
              {' '}
              <Link to={`/posts/${postId}/edit`} className="font-semibold text-accent underline">
                {t('compose.errors.editExisting')}
              </Link>
            </>
          )}
        </p>
      )
    }
    if (error.status === 422 && error.detail === 'season_invalid') {
      return <p>{t('compose.errors.season_invalid')}</p>
    }
  }
  return <p>{t('common.error')}</p>
}
