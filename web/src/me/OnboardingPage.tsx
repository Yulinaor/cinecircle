import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../api/client'
import type { Me } from '../api/types'
import { useApi } from '../api/useApi'
import { useAuth } from '../auth/AuthProvider'
import { currentLocale } from '../i18n'
import { LanguageChoice } from './LanguageChoice'
import { ME_KEY } from './useMe'

// Mirrors the API rule: trimmed, lower-cased, 3-30 of a-z 0-9 _ .
const USERNAME = /^[a-z0-9_.]{3,30}$/

const FIELD =
  'min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-base text-ink placeholder:text-muted'
const PRIMARY =
  'min-h-11 w-full rounded-xl bg-accent px-4 text-base font-semibold text-white disabled:opacity-60'

type ErrorKey = 'username_taken' | 'username_reserved' | 'username_invalid'
const KNOWN_ERRORS: readonly ErrorKey[] = ['username_taken', 'username_reserved', 'username_invalid']

function metadataName(metadata: unknown): string {
  const name =
    metadata && typeof metadata === 'object' && 'full_name' in metadata
      ? (metadata as { full_name?: unknown }).full_name
      : null
  return typeof name === 'string' ? name : ''
}

export function OnboardingPage() {
  const { t } = useTranslation()
  const api = useApi()
  const client = useQueryClient()
  const { session } = useAuth()
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState(() =>
    metadataName(session?.user?.user_metadata).slice(0, 50),
  )
  const [hintAsError, setHintAsError] = useState(false)
  const [error, setError] = useState<ErrorKey | 'generic' | null>(null)

  const create = useMutation({
    mutationFn: (body: { username: string; display_name: string; locale: 'he' | 'en' }) =>
      api<Me>('/me', { method: 'POST', body }),
    onSuccess: () => client.invalidateQueries({ queryKey: ME_KEY }),
    onError: (failure) => {
      if (failure instanceof ApiError && failure.detail === 'profile_exists') {
        // Another tab or request already created it: just continue into the app.
        void client.invalidateQueries({ queryKey: ME_KEY })
        return
      }
      const known = failure instanceof ApiError && KNOWN_ERRORS.find((k) => k === failure.detail)
      setError(known || 'generic')
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    const normalized = username.trim().toLowerCase()
    if (!USERNAME.test(normalized)) {
      setHintAsError(true)
      return
    }
    setHintAsError(false)
    create.mutate({
      username: normalized,
      display_name: displayName.trim(),
      locale: currentLocale(),
    })
  }

  return (
    <section className="mx-auto flex w-full max-w-sm flex-col gap-4 p-6">
      <h1 className="text-2xl font-extrabold">{t('onboarding.title')}</h1>
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t('onboarding.username')}
          <input
            type="text"
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            dir="ltr"
            maxLength={30}
            value={username}
            aria-describedby="username-hint"
            aria-invalid={hintAsError || undefined}
            onChange={(e) => {
              setUsername(e.target.value)
              setHintAsError(false)
              setError(null)
            }}
            className={FIELD}
          />
        </label>
        <p
          id="username-hint"
          role={hintAsError ? 'alert' : undefined}
          className={`text-sm ${hintAsError ? 'font-medium text-danger' : 'text-muted'}`}
        >
          {t('onboarding.usernameHint')}
        </p>
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t('onboarding.displayName')}
          <input
            type="text"
            name="display_name"
            autoComplete="name"
            required
            maxLength={50}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className={FIELD}
          />
        </label>
        <LanguageChoice label={t('onboarding.language')} />
        {error && (
          <p role="alert" className="text-sm font-medium text-danger">
            {error === 'generic' ? t('common.error') : t(`onboarding.errors.${error}`)}
          </p>
        )}
        <button
          type="submit"
          disabled={create.isPending || displayName.trim() === ''}
          className={PRIMARY}
        >
          {t('onboarding.submit')}
        </button>
      </form>
    </section>
  )
}
