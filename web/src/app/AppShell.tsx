import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomNav } from './BottomNav'
import { LanguageToggle } from './LanguageToggle'
import { AppRoutes } from './routes'

export function AppShell({ status }: { status?: ReactNode }) {
  const { t } = useTranslation()
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between gap-3 border-b border-line bg-surface px-4 py-3">
        <span className="text-xl font-extrabold tracking-tight">{t('app.name')}</span>
        <div className="flex items-center gap-3">
          {status}
          <LanguageToggle />
        </div>
      </header>
      <main className="flex-1 overflow-y-auto">
        <AppRoutes />
      </main>
      <BottomNav />
    </div>
  )
}
