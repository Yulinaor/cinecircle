import { useTranslation } from 'react-i18next'
import type { Lang } from '../api/types'
import { useLang } from '../i18n/useLang'

/**
 * Names a season (A6): TMDB's name only when it is in the UI language, else the localised
 * "Season N" — TMDB's other-language name is usually just "Season 1" and would need a label.
 */
export function useSeasonName(): (
  number: number,
  name: string | null,
  nameLang: Lang | null,
) => string {
  const { t } = useTranslation()
  const uiLang = useLang()
  return (number, name, nameLang) =>
    name !== null && nameLang === uiLang ? name : t('post.season', { n: number })
}
