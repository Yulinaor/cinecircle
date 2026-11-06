import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useNotifications } from './useNotifications'

const BADGE_MAX = 99

function badgeText(unread: number): string {
  return unread > BADGE_MAX ? `${BADGE_MAX}+` : String(unread)
}

/** Header link to the notifications page, with the unread count as a badge (hidden at zero). */
export function Bell() {
  const { t } = useTranslation()
  const unread = useNotifications().data?.unread_count ?? 0
  const text = badgeText(unread)
  return (
    <Link
      to="/notifications"
      aria-label={t('notifications.bell', { unread: text })}
      className="relative flex min-h-11 min-w-11 items-center justify-center rounded-xl bg-bg text-ink hover:bg-line"
    >
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="size-6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
        <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
      </svg>
      {unread > 0 && (
        <span
          aria-hidden="true"
          className="absolute -top-1 -end-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-danger px-1 text-xs font-bold text-white"
        >
          {text}
        </span>
      )}
    </Link>
  )
}
