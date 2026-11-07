import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'
import type { OnboardingBody, OnboardingState } from '../api/types'
import { useApi } from '../api/useApi'
import { GenreChips, MAX_GENRES } from './GenreChips'
import { QuizTitle, type QuizEntry } from './QuizTitle'

const MIN_GENRES = 3
const PRIMARY =
  'min-h-11 w-full rounded-xl bg-accent px-4 text-base font-semibold text-white disabled:opacity-60'
const SECONDARY =
  'min-h-11 w-full rounded-xl border border-line bg-surface px-4 text-base font-semibold text-ink hover:bg-bg disabled:opacity-60'

const entryKey = (e: QuizEntry) => `${e.media_type}:${e.tmdb_id}`

/**
 * The taste quiz: pick 3-5 genres and rate titles you have seen. Ratings are private (the API
 * stores them as private posts). Reached after sign-up and from Settings; can be skipped.
 */
export function TasteQuizPage() {
  const { t } = useTranslation()
  const api = useApi()
  const state = useQuery({
    queryKey: ['onboarding'],
    // Retaking the quiz starts from what is saved now, never from an older answer.
    gcTime: 0,
    queryFn: ({ signal }) => api<OnboardingState>('/onboarding', { signal }),
  })
  return (
    <section className="mx-auto flex w-full max-w-sm flex-col gap-4 p-6">
      <h1 className="text-2xl font-extrabold">{t('quiz.title')}</h1>
      <p className="text-sm text-muted">{t('quiz.private')}</p>
      {state.data ? (
        <QuizForm state={state.data} />
      ) : state.isError ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="text-sm font-medium text-danger">{t('common.error')}</p>
          <button type="button" onClick={() => void state.refetch()} className={SECONDARY}>
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

function QuizForm({ state }: { state: OnboardingState }) {
  const { t } = useTranslation()
  const api = useApi()
  const client = useQueryClient()
  const navigate = useNavigate()
  const [picked, setPicked] = useState<ReadonlySet<string>>(
    () => new Set(state.genres.filter((g) => g.picked).map((g) => g.key)),
  )
  // Ratings given in this visit, and the titles marked "Haven't seen it".
  const [ratings, setRatings] = useState<Record<string, { titleId: number; rating: number }>>({})
  const [skipped, setSkipped] = useState<ReadonlySet<string>>(new Set())

  const save = useMutation({
    mutationFn: (body: OnboardingBody) =>
      api<OnboardingState>('/onboarding', { method: 'POST', body }),
  })

  function toggle(key: string) {
    setPicked((now) => {
      const next = new Set(now)
      if (next.has(key)) next.delete(key)
      else if (next.size < MAX_GENRES) next.add(key)
      return next
    })
  }

  function skipTitle(key: string) {
    setSkipped((now) => new Set(now).add(key))
    setRatings(({ [key]: _dropped, ...rest }) => rest)
  }

  const count = Object.keys(ratings).length
  const ready = picked.size >= MIN_GENRES && picked.size <= MAX_GENRES

  function finish() {
    save.mutate(
      {
        genres: state.genres.filter((g) => picked.has(g.key)).map((g) => g.key),
        ratings: state.quiz.flatMap((e) => {
          const given = ratings[entryKey(e)]
          return given ? [{ title_id: given.titleId, rating: given.rating }] : []
        }),
      },
      {
        onSuccess: () => {
          // Taste Match now has data: every list that shows a score or a rating is out of date.
          for (const queryKey of [['me'], ['posts'], ['title'], ['wishlist']]) {
            void client.invalidateQueries({ queryKey })
          }
          void navigate('/')
        },
      },
    )
  }

  return (
    <>
      <p className="text-base font-medium">{t('quiz.genresHint')}</p>
      <GenreChips keys={state.genres.map((g) => g.key)} picked={picked} onToggle={toggle} />
      <h2 className="mt-2 text-lg font-bold">{t('quiz.titlesHeading')}</h2>
      <ul className="flex flex-col gap-3">
        {state.quiz.map((entry) => {
          const key = entryKey(entry)
          return (
            <QuizTitle
              key={key}
              entry={entry}
              value={ratings[key]?.rating ?? null}
              skipped={skipped.has(key)}
              onRate={(titleId, rating) =>
                setRatings((now) => ({ ...now, [key]: { titleId, rating } }))
              }
              onSkip={() => skipTitle(key)}
            />
          )
        })}
      </ul>
      <p role="status" className="text-sm font-medium text-muted">
        {t('quiz.progress', { count })}
      </p>
      {save.isError && (
        <p role="alert" className="text-sm font-medium text-danger">
          {t('common.error')}
        </p>
      )}
      <button type="button" onClick={finish} disabled={!ready || save.isPending} className={PRIMARY}>
        {t('quiz.finish')}
      </button>
      <button type="button" onClick={() => void navigate('/')} className={SECONDARY}>
        {t('quiz.skip')}
      </button>
    </>
  )
}
