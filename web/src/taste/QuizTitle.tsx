import { useQuery } from '@tanstack/react-query'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import type { OnboardingState, TitleDetail } from '../api/types'
import { useApi } from '../api/useApi'
import { RatingInput } from '../compose/RatingInput'
import { LangLabel } from '../i18n/LangLabel'
import { useLang } from '../i18n/useLang'
import { useActionName } from '../people/actionName'

export type QuizEntry = OnboardingState['quiz'][number]

const SECONDARY =
  'min-h-11 self-start rounded-xl border border-line bg-surface px-4 text-base font-medium text-ink hover:bg-line'

/**
 * One quiz title: it loads its own details (which also caches the title and gives the id to send),
 * then offers a rating and "Haven't seen it". A title that already has a rating shows it instead.
 * A title that fails to load is left out.
 */
export function QuizTitle({
  entry,
  value,
  skipped,
  onRate,
  onSkip,
}: {
  entry: QuizEntry
  /** The rating given in this visit. */
  value: number | null
  skipped: boolean
  onRate: (titleId: number, rating: number) => void
  onSkip: () => void
}) {
  const { t } = useTranslation()
  const api = useApi()
  const lang = useLang()
  const nameId = useId()
  const notSeenName = useActionName(nameId)
  const title = useQuery({
    queryKey: ['title', 'tmdb', entry.media_type, entry.tmdb_id, lang],
    queryFn: ({ signal }) =>
      api<TitleDetail>(`/titles/tmdb/${entry.media_type}/${entry.tmdb_id}?lang=${lang}`, {
        signal,
      }),
  })

  if (title.isError) return null
  if (!title.data) {
    return <li aria-hidden="true" className="h-44 rounded-2xl bg-line/50" />
  }
  const detail = title.data

  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4">
      <div className="flex items-center gap-3">
        {detail.poster_url ? (
          <img
            src={detail.poster_url}
            alt=""
            className="aspect-[2/3] w-16 shrink-0 rounded-xl bg-line object-cover"
          />
        ) : (
          <div aria-hidden="true" className="aspect-[2/3] w-16 shrink-0 rounded-xl bg-line" />
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <h3 id={nameId} dir="auto" className="text-lg font-bold leading-snug text-ink">
            {detail.name}
          </h3>
          <LangLabel lang={detail.name_lang} />
          {detail.year_start !== null && (
            <p className="text-sm text-muted">
              <bdi>{detail.year_start}</bdi>
            </p>
          )}
        </div>
      </div>
      {entry.my_rating !== null ? (
        <p className="text-sm font-medium text-ink">
          {t('quiz.yourRating')} <bdi className="font-bold">{entry.my_rating.toFixed(1)}</bdi>
        </p>
      ) : (
        !skipped && (
          <>
            <RatingInput
              value={value}
              titleNameId={nameId}
              onChange={(rating) => onRate(detail.id, rating)}
            />
            <button type="button" {...notSeenName} onClick={onSkip} className={SECONDARY}>
              {t('quiz.notSeen')}
            </button>
          </>
        )
      )}
    </li>
  )
}
