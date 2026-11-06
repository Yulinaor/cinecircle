import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { supabase } from './supabase'

type Mode = 'sign_in' | 'sign_up'
type ErrorKey =
  | 'invalid_credentials'
  | 'email_not_confirmed'
  | 'user_already_exists'
  | 'weak_password'
  | 'generic'

const KNOWN_ERRORS: readonly ErrorKey[] = [
  'invalid_credentials',
  'email_not_confirmed',
  'user_already_exists',
  'weak_password',
]

function errorKey(error: unknown): ErrorKey {
  const code =
    error && typeof error === 'object' && 'code' in error ? (error as { code?: unknown }).code : null
  return KNOWN_ERRORS.find((known) => known === code) ?? 'generic'
}

const FIELD =
  'min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-base text-ink placeholder:text-muted'
const PRIMARY =
  'min-h-11 w-full rounded-xl bg-accent px-4 text-base font-semibold text-white disabled:opacity-60'
const SECONDARY =
  'min-h-11 w-full rounded-xl border border-line bg-surface px-4 text-base font-semibold text-ink hover:bg-bg disabled:opacity-60'

export function SignInPage() {
  const { t } = useTranslation()
  const [mode, setMode] = useState<Mode>('sign_in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ErrorKey | null>(null)
  const [checkEmail, setCheckEmail] = useState(false)

  const heading = mode === 'sign_in' ? t('auth.signIn') : t('auth.signUp')

  if (!supabase) {
    return (
      <section className="mx-auto flex w-full max-w-sm flex-col gap-4 p-6">
        <h1 className="text-2xl font-extrabold">{heading}</h1>
        <p role="alert" className="rounded-xl bg-surface p-4 text-muted">
          {t('auth.unconfigured')}
        </p>
      </section>
    )
  }
  const client = supabase

  if (checkEmail) {
    return (
      <section className="mx-auto flex w-full max-w-sm flex-col gap-4 p-6">
        <h1 className="text-2xl font-extrabold">{t('auth.signUp')}</h1>
        <p role="status" className="rounded-xl bg-accent-soft p-4 text-ink">
          {t('auth.checkEmail')}
        </p>
        <button
          type="button"
          className={SECONDARY}
          onClick={() => {
            setCheckEmail(false)
            setMode('sign_in')
          }}
        >
          {t('auth.switchToSignIn')}
        </button>
      </section>
    )
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'sign_in') {
        const { error: failure } = await client.auth.signInWithPassword({ email, password })
        if (failure) setError(errorKey(failure))
      } else {
        const { data, error: failure } = await client.auth.signUp({ email, password })
        if (failure) {
          setError(errorKey(failure))
        } else if (data?.user?.identities?.length === 0) {
          // Supabase hides "already registered" behind a fake user with no identities.
          setError('user_already_exists')
        } else if (!data?.session) {
          setCheckEmail(true)
        }
      }
    } catch {
      setError('generic')
    } finally {
      setBusy(false)
    }
  }

  async function google() {
    setBusy(true)
    setError(null)
    try {
      const { error: failure } = await client.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: window.location.origin },
      })
      if (failure) setError(errorKey(failure))
    } catch {
      setError('generic')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mx-auto flex w-full max-w-sm flex-col gap-4 p-6">
      <h1 className="text-2xl font-extrabold">{heading}</h1>
      <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t('auth.email')}
          <input
            type="email"
            name="email"
            autoComplete="email"
            dir="ltr"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={FIELD}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t('auth.password')}
          <input
            type="password"
            name="password"
            autoComplete={mode === 'sign_in' ? 'current-password' : 'new-password'}
            dir="ltr"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={FIELD}
          />
        </label>
        {error && (
          <p role="alert" className="text-sm font-medium text-danger">
            {t(`auth.errors.${error}`)}
          </p>
        )}
        <button type="submit" disabled={busy} className={PRIMARY}>
          {heading}
        </button>
      </form>
      <button type="button" disabled={busy} onClick={() => void google()} className={SECONDARY}>
        {t('auth.google')}
      </button>
      <button
        type="button"
        onClick={() => {
          setMode(mode === 'sign_in' ? 'sign_up' : 'sign_in')
          setError(null)
        }}
        className="min-h-11 text-sm font-semibold text-accent"
      >
        {mode === 'sign_in' ? t('auth.switchToSignUp') : t('auth.switchToSignIn')}
      </button>
    </section>
  )
}
