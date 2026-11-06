import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { Me } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { currentLocale, setLocale } from '../i18n'
import { ME_KEY, useUpdateMe } from '../me/useMe'

export function LanguageToggle() {
  const { t } = useTranslation()
  const { status } = useAuth()
  const client = useQueryClient()
  const updateMe = useUpdateMe()
  const next = currentLocale() === 'he' ? 'en' : 'he'

  function toggle() {
    void setLocale(next)
    // Fire-and-forget: the UI has already switched; a failed save just leaves the account as it was.
    if (status === 'signed_in' && client.getQueryData<Me>(ME_KEY)?.profile) {
      updateMe.mutate({ locale: next })
    }
  }

  return (
    <button
      type="button"
      aria-label={t('language.label')}
      onClick={toggle}
      className="min-h-11 rounded-xl bg-bg px-3 text-sm font-semibold text-ink hover:bg-line"
    >
      {t('language.switchTo')}
    </button>
  )
}
