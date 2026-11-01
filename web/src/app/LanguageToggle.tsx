import { useTranslation } from 'react-i18next'
import { currentLocale, setLocale } from '../i18n'

export function LanguageToggle() {
  const { t } = useTranslation()
  const next = currentLocale() === 'he' ? 'en' : 'he'
  return (
    <button
      type="button"
      aria-label={t('language.label')}
      onClick={() => void setLocale(next)}
      className="min-h-11 rounded-xl bg-bg px-3 text-sm font-semibold text-ink hover:bg-line"
    >
      {t('language.switchTo')}
    </button>
  )
}
