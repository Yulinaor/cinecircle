import { useTranslation } from 'react-i18next'
import { useApiStatus, type ApiStatus as Status } from '../api/useApiStatus'

const DOT: Record<Status, string> = {
  checking: 'bg-muted',
  waking: 'bg-amber-500',
  connected: 'bg-emerald-600',
  offline: 'bg-red-600',
}

export function ApiStatus() {
  const { t } = useTranslation()
  const status = useApiStatus()
  if (status === 'waking') {
    // The free server takes a while to wake, so say so where it can be seen on a phone, not in a
    // dot. `fixed` keeps it out of the layout; 4.5rem clears the header (two 44 px controls
    // plus padding and border), and the banner can never be wider than the screen.
    return (
      <>
        <span aria-hidden="true" className={`size-2.5 shrink-0 rounded-full ${DOT[status]}`} />
        <p
          role="status"
          className="fixed inset-x-4 top-[4.5rem] z-20 rounded-xl border border-amber-500 bg-amber-50 px-4 py-2 text-center text-sm font-medium text-ink shadow-sm"
        >
          {t('api.waking')}
        </p>
      </>
    )
  }
  return (
    <span
      role="status"
      title={t(`api.${status}`)}
      className="flex items-center gap-1.5 text-xs font-medium text-muted"
    >
      <span aria-hidden="true" className={`size-2.5 shrink-0 rounded-full ${DOT[status]}`} />
      {/* Dot only on phones; the text stays available to screen readers. */}
      <span className="sr-only sm:not-sr-only">{t(`api.${status}`)}</span>
    </span>
  )
}
