import { useTranslation } from 'react-i18next'
import type { Locale } from './index'

/** The UI language (`he` | `en`); components re-render when it changes. */
export function useLang(): Locale {
  const { i18n } = useTranslation()
  return i18n.language === 'en' ? 'en' : 'he'
}
