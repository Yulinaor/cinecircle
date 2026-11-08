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
  const text = t(`api.${status}`)
  // One status node for every state: a live region announces text that changes inside it, but
  // often skips a region that is inserted already holding text, so the node never goes away.
  return (
    <span
      role="status"
      title={text}
      className="flex items-center gap-1.5 text-xs font-medium text-muted"
    >
      <span aria-hidden="true" className={`size-2.5 shrink-0 rounded-full ${DOT[status]}`} />
      {status === 'waking' ? (
        // The free server takes a while to wake, so say so where a phone can see it, not in a dot.
        // `fixed` takes it out of the header's layout; 4.5rem clears the header (two 44 px
        // controls plus padding and border), and inset-x-4 keeps it inside the screen.
        <span className="fixed inset-x-4 top-[4.5rem] z-20 rounded-xl border border-amber-500 bg-amber-50 px-4 py-2 text-center text-sm font-medium text-ink shadow-sm">
          {text}
        </span>
      ) : (
        // Dot only on phones; the text stays available to screen readers.
        <span className="sr-only sm:not-sr-only">{text}</span>
      )}
    </span>
  )
}
