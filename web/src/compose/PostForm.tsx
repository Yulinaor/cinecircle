import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { RatingInput } from './RatingInput'

const OPINION_MAX = 500

export type PostFormValues = {
  rating: number
  /** Trimmed; null when empty. */
  opinion: string | null
  contains_spoilers: boolean
  is_shared: boolean
}

export type PostFormInitial = Omit<PostFormValues, 'rating'> & { rating: number | null }

const EMPTY_POST: PostFormInitial = {
  rating: null,
  opinion: null,
  contains_spoilers: false,
  is_shared: true,
}

const PRIMARY =
  'min-h-11 w-full rounded-xl bg-accent px-4 text-base font-semibold text-white disabled:opacity-60'
const OPTION = 'flex min-h-11 items-center gap-3 rounded-xl border border-line bg-surface px-3'

/** Rating, opinion, spoiler flag and who sees it: the part of a post you can write and change. */
export function PostForm({
  initial = EMPTY_POST,
  onSubmit,
  submitLabel,
  busy = false,
  error,
}: {
  initial?: PostFormInitial
  onSubmit: (values: PostFormValues) => void
  submitLabel: string
  /** Disables Post while a request is on its way. */
  busy?: boolean
  /** Shown above the button, e.g. why the last attempt failed. */
  error?: ReactNode
}) {
  const { t } = useTranslation()
  const countId = useId()
  const [rating, setRating] = useState(initial.rating)
  const [opinion, setOpinion] = useState(initial.opinion ?? '')
  const [spoilers, setSpoilers] = useState(initial.contains_spoilers)
  const [shared, setShared] = useState(initial.is_shared)

  // What is sent (and counted) is the trimmed text; characters are code points, as in Postgres.
  const trimmed = opinion.trim()
  const length = Array.from(trimmed).length
  const tooLong = length > OPINION_MAX

  function submit(event: FormEvent) {
    event.preventDefault()
    if (rating === null || tooLong || busy) return
    onSubmit({
      rating,
      opinion: trimmed === '' ? null : trimmed,
      contains_spoilers: spoilers,
      is_shared: shared,
    })
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <RatingInput value={rating} onChange={setRating} />
      <div className="flex flex-col gap-1">
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t('compose.opinion')}
          <textarea
            name="opinion"
            rows={4}
            dir="auto"
            value={opinion}
            aria-invalid={tooLong}
            aria-describedby={countId}
            onChange={(e) => setOpinion(e.target.value)}
            className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-base font-normal text-ink placeholder:text-muted"
          />
        </label>
        <span id={countId} className={`text-xs ${tooLong ? 'text-danger' : 'text-muted'}`}>
          <bdi>{t('compose.opinionCount', { n: length, max: OPINION_MAX })}</bdi>
        </span>
        {tooLong && (
          <p role="alert" className="text-sm font-medium text-danger">
            {t('compose.errors.opinion_too_long', { max: OPINION_MAX })}
          </p>
        )}
      </div>
      <label className={OPTION}>
        <input
          type="checkbox"
          name="contains_spoilers"
          checked={spoilers}
          onChange={(e) => setSpoilers(e.target.checked)}
          className="size-4 accent-accent"
        />
        {t('compose.spoiler')}
      </label>
      <fieldset role="radiogroup" className="flex flex-col gap-1">
        <label className={OPTION}>
          <input
            type="radio"
            name="is_shared"
            checked={shared}
            onChange={() => setShared(true)}
            className="size-4 accent-accent"
          />
          {t('compose.share')}
        </label>
        <label className={OPTION}>
          <input
            type="radio"
            name="is_shared"
            checked={!shared}
            onChange={() => setShared(false)}
            className="size-4 accent-accent"
          />
          {t('compose.keepPrivate')}
        </label>
      </fieldset>
      {error && (
        <div role="alert" className="text-sm font-medium text-danger">
          {error}
        </div>
      )}
      <button type="submit" disabled={rating === null || tooLong || busy} className={PRIMARY}>
        {submitLabel}
      </button>
    </form>
  )
}
