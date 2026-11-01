import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import he from './he.json'

export const SUPPORTED_LOCALES = ['he', 'en'] as const
export type Locale = (typeof SUPPORTED_LOCALES)[number]
export const DEFAULT_LOCALE: Locale = 'he'
export const LOCALE_STORAGE_KEY = 'cinecircle.locale'

const DIRECTION: Record<Locale, 'rtl' | 'ltr'> = { he: 'rtl', en: 'ltr' }

function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (SUPPORTED_LOCALES as readonly string[]).includes(value)
}

/** localStorage, or null when the browser blocks it (private mode, sandboxed frames). */
function safeLocalStorage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export function resolveInitialLocale(storage: Pick<Storage, 'getItem'> | null): Locale {
  try {
    const stored = storage?.getItem(LOCALE_STORAGE_KEY)
    return isLocale(stored) ? stored : DEFAULT_LOCALE
  } catch {
    return DEFAULT_LOCALE
  }
}

export function applyDocumentLocale(locale: Locale, doc: Document = document): void {
  doc.documentElement.lang = locale
  doc.documentElement.dir = DIRECTION[locale]
}

export async function setLocale(locale: Locale): Promise<void> {
  await i18n.changeLanguage(locale)
  applyDocumentLocale(locale)
  try {
    safeLocalStorage()?.setItem(LOCALE_STORAGE_KEY, locale)
  } catch {
    // Storage full or blocked: the choice still applies for this visit.
  }
}

export function initI18n(): typeof i18n {
  if (!i18n.isInitialized) {
    const lng = resolveInitialLocale(safeLocalStorage())
    void i18n.use(initReactI18next).init({
      resources: { he: { translation: he }, en: { translation: en } },
      lng,
      fallbackLng: DEFAULT_LOCALE,
      supportedLngs: [...SUPPORTED_LOCALES],
      interpolation: { escapeValue: false },
      initAsync: false,
    })
    applyDocumentLocale(lng)
  }
  return i18n
}

export function currentLocale(): Locale {
  return isLocale(i18n.language) ? i18n.language : DEFAULT_LOCALE
}
