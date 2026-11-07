import { useTranslation } from 'react-i18next'

/** What this product is built on: the TMDB notice TMDB requires, and where the ratings come from. */
export function About() {
  const { t } = useTranslation()
  return (
    <section aria-labelledby="settings-about" className="flex flex-col gap-2">
      <h2 id="settings-about" className="text-lg font-bold text-ink">
        {t('about.heading')}
      </h2>
      <p className="text-sm text-muted">
        <a
          href="https://www.themoviedb.org/"
          target="_blank"
          rel="noopener noreferrer"
          className="me-2 inline-flex min-h-11 items-center font-extrabold tracking-wide text-accent underline"
        >
          TMDB
        </a>
        {t('about.tmdbNotice')}
      </p>
      <p className="text-sm text-muted">{t('about.omdb')}</p>
    </section>
  )
}
