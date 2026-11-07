import { useEffect, useId, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import type { NotificationItem } from '../api/types'
import { RequestActions } from '../people/ConnectionActions'
import { Avatar } from '../people/Avatar'
import { useMarkNotificationsRead, useNotifications } from './useNotifications'

export function NotificationsPage() {
  const { t } = useTranslation()
  const list = useNotifications()
  const { mutate: markRead } = useMarkNotificationsRead()

  // Opening the page counts as reading: mark everything read once per visit, then refetch.
  const marked = useRef(false)
  useEffect(() => {
    if (marked.current) return
    marked.current = true
    markRead()
  }, [markRead])

  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      <h1 className="text-2xl font-extrabold">{t('notifications.title')}</h1>
      {list.isError ? (
        <p role="alert" className="text-sm font-medium text-danger">
          {t('common.error')}
        </p>
      ) : !list.data ? (
        <p role="status" className="text-muted">
          {t('auth.loading')}
        </p>
      ) : list.data.items.length === 0 ? (
        <p className="text-muted">{t('notifications.empty')}</p>
      ) : (
        <>
          <ul className="flex flex-col gap-2">
            {list.data.items.map((item) => (
              <NotificationRow key={item.id} item={item} />
            ))}
          </ul>
          {list.data.next_cursor !== null && (
            <button
              type="button"
              onClick={() => void list.fetchNextPage()}
              disabled={list.isFetchingNextPage}
              className="min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line disabled:opacity-60"
            >
              {t('common.loadMore')}
            </button>
          )}
        </>
      )}
    </section>
  )
}

function NotificationRow({ item }: { item: NotificationItem }) {
  const { t } = useTranslation()
  const nameId = useId()
  const key = item.type === 'follow_request' ? 'notifications.followRequest' : 'notifications.followAccepted'
  return (
    <li
      className={`flex items-center gap-3 rounded-2xl border p-3 ${
        item.read ? 'border-line bg-surface' : 'border-accent bg-accent-soft'
      }`}
    >
      <Avatar url={item.actor.avatar_url} name={item.actor.display_name} />
      <p className="min-w-0 flex-1 text-ink">{t(key, { name: item.actor.display_name })}</p>
      <span id={nameId} hidden>
        {item.actor.display_name}
      </span>
      {item.type === 'follow_request' && item.request_pending && (
        <RequestActions username={item.actor.username} nameId={nameId} />
      )}
    </li>
  )
}
