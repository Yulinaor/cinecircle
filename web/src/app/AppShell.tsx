import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthProvider'
import { SignInPage } from '../auth/SignInPage'
import { BottomNav } from './BottomNav'
import { LanguageToggle } from './LanguageToggle'
import { AppRoutes } from './routes'

export function AppShell({ status }: { status?: ReactNode }) {
  const { t } = useTranslation()
  const { status: authStatus, signOut } = useAuth()
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between gap-3 border-b border-line bg-surface px-4 py-3">
        <span className="text-xl font-extrabold tracking-tight">{t('app.name')}</span>
        <div className="flex items-center gap-3">
          {status}
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
      {authStatus === 'loading' && (
        <main className="flex flex-1 items-center justify-center">
          <p role="status" className="text-muted">
            {t('auth.loading')}
          </p>
        </main>
      )}
      {authStatus === 'signed_out' && (
        <main className="flex-1 overflow-y-auto">
          <SignInPage />
        </main>
      )}
      {authStatus === 'signed_in' && (
        <>
          <main className="flex-1 overflow-y-auto">
            <AppRoutes />
          </main>
          <BottomNav />
        </>
      )}
    </div>
  )
}
