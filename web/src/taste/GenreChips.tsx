import { useTranslation } from 'react-i18next'

/** Most genres a person can pick; the API refuses a sixth. */
export const MAX_GENRES = 5

/**
 * The genre chips: toggles (`aria-pressed`) that wrap onto as many lines as they need. Once
 * `MAX_GENRES` are picked the other chips are disabled; picked ones can always be undone.
 */
export function GenreChips({
  keys,
  picked,
  onToggle,
}: {
  keys: string[]
  picked: ReadonlySet<string>
  onToggle: (key: string) => void
}) {
  const { t } = useTranslation()
  const full = picked.size >= MAX_GENRES
  return (
    <ul className="flex flex-wrap gap-2">
      {keys.map((key) => {
        const on = picked.has(key)
        return (
          <li key={key}>
            <button
              type="button"
              aria-pressed={on}
              disabled={!on && full}
              onClick={() => onToggle(key)}
              className={`min-h-11 rounded-full border px-4 text-base font-medium disabled:opacity-40 ${
                on
                  ? 'border-accent bg-accent text-white'
                  : 'border-line bg-surface text-ink hover:bg-line'
              }`}
            >
              {t(`quiz.genre.${key}`)}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
