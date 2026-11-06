import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useUserScopedCache } from '../api/useUserScopedCache'
import { useAuth } from '../auth/AuthProvider'
import { SignInPage } from '../auth/SignInPage'
import { OnboardingPage } from '../me/OnboardingPage'
import { useMe } from '../me/useMe'
import { BottomNav } from './BottomNav'
import { LanguageToggle } from './LanguageToggle'
import { AppRoutes } from './routes'

export function AppShell({ status }: { status?: ReactNode }) {
  const { t } = useTranslation()
  const { status: authStatus, session, signOut } = useAuth()
  // Cached account data must never outlive the user that fetched it (also for A -> B switches).
  const cacheReady = useUserScopedCache(session?.user.id ?? null)
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between gap-3 border-b border-line bg-surface px-4 py-3">
        <span className="text-xl font-extrabold tracking-tight">{t('app.name')}</span>
        <div className="flex items-center gap-3">
          {status}
          {authStatus === 'signed_in' && cacheReady && <SettingsLink />}
          <LanguageToggle />
          {authStatus === 'signed_in' && (
            <button
              type="button"
              onClick={() => void signOut()}
              className="min-h-11 rounded-xl bg-bg px-3 text-sm font-semibold text-ink hover:bg-line"
            >
              {t('auth.signOut')}
            </button>
          )}
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

/** Visible once the account has a profile; the page itself is also a route. */
function SettingsLink() {
  const { t } = useTranslation()
  const me = useMe()
  if (!me.data?.profile) return null
  return (
    <Link
      to="/settings"
      className="flex min-h-11 items-center rounded-xl bg-bg px-3 text-sm font-semibold text-ink hover:bg-line"
    >
      {t('settings.title')}
    </Link>
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
