import { useTranslation } from 'react-i18next'

export function Placeholder({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation()
  return (
    <section className="mx-auto flex max-w-xl flex-col gap-2 px-4 py-8">
      <h1 className="text-2xl font-extrabold text-ink">{t(titleKey)}</h1>
      <p className="text-muted">{t('placeholder.comingSoon')}</p>
    </section>
  )
}
