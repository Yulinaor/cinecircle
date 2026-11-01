import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router'
import { TABS } from './tabs'

export function BottomNav() {
  const { t } = useTranslation()
  return (
    <nav className="grid grid-cols-5 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]">
      {TABS.map((tab) => (
        <NavLink
          key={tab.path}
          to={tab.path}
          end={tab.path === '/'}
          className={({ isActive }) =>
            `flex min-h-14 items-center justify-center px-1 text-center text-xs font-semibold ${
              isActive ? 'text-accent' : 'text-muted hover:text-ink'
            }`
          }
        >
          {t(tab.labelKey)}
        </NavLink>
      ))}
    </nav>
  )
}
