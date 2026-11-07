import { useId } from 'react'
import { useTranslation } from 'react-i18next'

const MIN = 1
const MAX = 10
const STEP = 0.5
/** Where the slider rests, and where the − / + buttons start from, while nothing is chosen. */
const MIDDLE = 5.5

/** The value if it is on the ½ grid within 1–10, else null. */
function valid(value: number): number | null {
  return Number.isFinite(value) && value >= MIN && value <= MAX && Number.isInteger(value * 2)
    ? value
    : null
}

const BUTTON =
  'min-h-11 min-w-11 rounded-xl border border-line bg-surface text-xl font-semibold text-ink hover:bg-line'

/**
 * A 1–10 rating in half steps. Starts unset ("—"). A native range input (so the keyboard and
 * screen readers work as expected) with − / + buttons; it never emits anything off the grid.
 */
export function RatingInput({
  value,
  onChange,
}: {
  value: number | null
  onChange: (value: number) => void
}) {
  const { t } = useTranslation()
  const id = useId()

  function emit(next: number) {
    const ok = valid(Math.min(MAX, Math.max(MIN, next)))
    if (ok !== null && ok !== value) onChange(ok)
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium">
          {t('compose.rating')}
        </label>
        <bdi aria-hidden="true" className="text-3xl font-extrabold text-ink">
          {value === null ? '—' : value.toFixed(1)}
        </bdi>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label={t('compose.decrease')}
          onClick={() => emit((value ?? MIDDLE) - STEP)}
          className={BUTTON}
        >
          −
        </button>
        <input
          id={id}
          type="range"
          min={MIN}
          max={MAX}
          step={STEP}
          value={value ?? MIDDLE}
          aria-valuetext={value === null ? t('compose.ratingUnset') : value.toFixed(1)}
          onChange={(e) => {
            const next = valid(Number(e.target.value))
            if (next !== null) onChange(next)
          }}
          className={`min-h-11 min-w-0 flex-1 accent-accent ${value === null ? 'opacity-50' : ''}`}
        />
        <button
          type="button"
          aria-label={t('compose.increase')}
          onClick={() => emit((value ?? MIDDLE) + STEP)}
          className={BUTTON}
        >
          +
        </button>
      </div>
    </div>
  )
}
