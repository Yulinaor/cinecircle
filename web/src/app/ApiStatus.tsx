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
  return (
    <span role="status" className="flex items-center gap-1.5 text-xs font-medium text-muted">
      <span aria-hidden="true" className={`size-2 rounded-full ${DOT[status]}`} />
      {t(`api.${status}`)}
    </span>
  )
}
