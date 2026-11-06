import { useTranslation } from 'react-i18next'
import { currentLocale, setLocale, SUPPORTED_LOCALES, type Locale } from '../i18n'

// Language names stay in their own language so they're recognisable whatever the UI shows.
const NAMES: Record<Locale, string> = { he: 'עברית', en: 'English' }

/** Two-button language picker. Switches the UI immediately, then tells the caller. */
export function LanguageChoice({
  label,
  onChange,
}: {
  label: string
  onChange?: (locale: Locale) => void
}) {
  // Subscribing to i18n re-renders this when the language changes.
  useTranslation()
  const active = currentLocale()
  return (
    <div role="group" aria-label={label} className="flex flex-col gap-1 text-sm font-medium">
      <span aria-hidden="true">{label}</span>
      <div className="flex gap-2">
        {SUPPORTED_LOCALES.map((locale) => (
          <button
            key={locale}
            type="button"
            lang={locale}
            aria-pressed={locale === active}
            onClick={() => {
              void setLocale(locale)
              onChange?.(locale)
            }}
            className={`min-h-11 flex-1 rounded-xl border px-4 text-base font-semibold ${
              locale === active
                ? 'border-accent bg-accent-soft text-accent'
                : 'border-line bg-surface text-ink hover:bg-bg'
            }`}
          >
            {NAMES[locale]}
          </button>
        ))}
      </div>
    </div>
  )
}
