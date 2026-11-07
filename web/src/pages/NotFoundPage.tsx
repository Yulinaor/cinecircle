import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

/** Unknown route, or a page whose thing the API says does not exist (or is hidden from you). */
export function NotFoundPage() {
  const { t } = useTranslation()
  return (
    <section className="mx-auto flex w-full max-w-xl flex-col items-start gap-3 px-4 py-10">
      <h1 className="text-2xl font-extrabold text-ink">{t('notFound.title')}</h1>
      <p className="text-muted">{t('notFound.body')}</p>
      <Link
        to="/"
        className="inline-flex min-h-11 items-center rounded-xl border border-line bg-surface px-4 font-medium text-accent hover:bg-line"
      >
        {t('notFound.home')}
      </Link>
    </section>
  )
}
