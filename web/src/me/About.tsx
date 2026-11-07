import { useTranslation } from 'react-i18next'
// TMDB's official compact logo, from themoviedb.org/about/logos-attribution.
import tmdbLogo from '../assets/tmdb-logo.svg'

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
          className="me-2 inline-flex min-h-11 items-center"
        >
          <img src={tmdbLogo} alt="TMDB" className="h-3 w-auto" />
        </a>
        {t('about.tmdbNotice')}
      </p>
      <p className="text-sm text-muted">{t('about.omdb')}</p>
    </section>
  )
}
