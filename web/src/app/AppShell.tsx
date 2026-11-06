import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useUserScopedCache } from '../api/useUserScopedCache'
import { useAuth } from '../auth/AuthProvider'
import { SignInPage } from '../auth/SignInPage'
import { OnboardingPage } from '../me/OnboardingPage'
import { useMe } from '../me/useMe'
import { Bell } from '../notifications/Bell'
import { BottomNav } from './BottomNav'
import { LanguageToggle } from './LanguageToggle'
import { AppRoutes } from './routes'

export function AppShell({ status }: { status?: ReactNode }) {
  const { t } = useTranslation()
  const { status: authStatus, session } = useAuth()
  // Cached account data must never outlive the user that fetched it (also for A -> B switches).
  const cacheReady = useUserScopedCache(session?.user.id ?? null)
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between gap-3 border-b border-line bg-surface px-4 py-3">
        <span className="shrink-0 text-xl font-extrabold tracking-tight">{t('app.name')}</span>
        <div className="flex min-w-0 items-center gap-2">
          {status}
          {authStatus === 'signed_in' && (cacheReady ? <AccountControls /> : <SignOutButton />)}
          <LanguageToggle />
        </div>
      </header>
      {authStatus === 'loading' && <Loading />}
      {authStatus === 'signed_out' && (
        <main className="flex-1 overflow-y-auto">
          <SignInPage />
        </main>
      )}
      {authStatus === 'signed_in' && (cacheReady ? <SignedInBody /> : <Loading />)}
    </div>
  )
}

function Loading() {
  const { t } = useTranslation()
  return (
    <main className="flex flex-1 items-center justify-center">
      <p role="status" className="text-muted">
        {t('auth.loading')}
      </p>
    </main>
  )
}

function SignOutButton() {
  const { t } = useTranslation()
  const { signOut } = useAuth()
  return (
    <button
      type="button"
      onClick={() => void signOut()}
      className="min-h-11 rounded-xl bg-bg px-3 text-sm font-semibold text-ink hover:bg-line"
    >
      {t('auth.signOut')}
    </button>
  )
}

/**
 * Header controls once the account is known. With a profile: icon-only notifications and settings
 * (settings has the sign-out button). Without one (onboarding) there is no settings page, so the
 * header keeps a sign-out button. Each page is also a route.
 */
function AccountControls() {
  const { t } = useTranslation()
  const me = useMe()
  if (!me.data?.profile) return <SignOutButton />
  return (
    <>
      <Bell />
      <Link
        to="/settings"
        aria-label={t('settings.title')}
        className="flex min-h-11 min-w-11 items-center justify-center rounded-xl bg-bg text-ink hover:bg-line"
      >
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          className="size-6"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </Link>
    </>
  )
}

/** Signed in: wait for the account, make a username first if there's no profile, then the app. */
function SignedInBody() {
  const { t } = useTranslation()
  const me = useMe()
  if (me.isPending) return <Loading />
  if (me.isError) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center gap-3 p-6">
        <p role="alert" className="font-medium text-danger">
          {t('common.error')}
        </p>
        <button
          type="button"
          onClick={() => void me.refetch()}
          className="min-h-11 rounded-xl bg-accent px-4 text-base font-semibold text-white"
        >
          {t('common.retry')}
        </button>
      </main>
    )
  }
  if (!me.data.profile) {
    return (
      <main className="flex-1 overflow-y-auto">
        <OnboardingPage />
      </main>
    )
  }
  return (
    <>
      <main className="flex-1 overflow-y-auto">
        <AppRoutes />
      </main>
      <BottomNav />
    </>
  )
}
