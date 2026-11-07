import { useTranslation } from 'react-i18next'
import type { Season } from '../api/types'
import { useSeasonName } from '../posts/seasonName'

/**
 * Whole series (0) or one season of it. TMDB's "Specials" is season 0 too, so it is not offered:
 * it would clash with the whole series.
 */
export function SeasonPicker({
  seasons,
  value,
  onChange,
}: {
  seasons: Season[]
  value: number
  onChange: (season: number) => void
}) {
  const { t } = useTranslation()
  const seasonName = useSeasonName()
  const options = [
    { number: 0, label: t('post.wholeSeries') },
    ...seasons
      .filter((s) => s.season_number > 0)
      .map((s) => ({
        number: s.season_number,
        label: seasonName(s.season_number, s.name, s.name_lang),
      })),
  ]
  return (
    <fieldset role="radiogroup" className="flex flex-col gap-1">
      <legend className="mb-1 text-sm font-medium">{t('compose.season')}</legend>
      {options.map((option) => (
        <label
          key={option.number}
          className="flex min-h-11 items-center gap-3 rounded-xl border border-line bg-surface px-3"
        >
          <input
            type="radio"
            name="season"
            checked={value === option.number}
            onChange={() => onChange(option.number)}
            className="size-4 accent-accent"
          />
          <span dir="auto">{option.label}</span>
        </label>
      ))}
    </fieldset>
  )
}
