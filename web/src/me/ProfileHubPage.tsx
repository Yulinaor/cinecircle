import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

const LINKS = [
  { to: '/connections', labelKey: 'connections.title' },
  { to: '/people', labelKey: 'people.title' },
  { to: '/settings', labelKey: 'settings.title' },
] as const

/** The Profile tab until Phase 3 brings the real profile: just the way to the account screens. */
export function ProfileHubPage() {
  const { t } = useTranslation()
  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      <h1 className="text-2xl font-extrabold">{t('nav.profile')}</h1>
      <ul className="flex flex-col gap-2">
        {LINKS.map((link) => (
          <li key={link.to}>
            <Link
              to={link.to}
              className="flex min-h-12 items-center rounded-2xl border border-line bg-surface px-4 text-base font-semibold text-ink hover:bg-bg"
            >
              {t(link.labelKey)}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
