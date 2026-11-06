import { useQuery } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { UserCard } from '../api/types'
import { useApi } from '../api/useApi'
import { RemoveFollower, RequestActions } from './ConnectionActions'
import { FollowButton } from './FollowButton'
import { UserCardRow } from './UserCardRow'

const TABS = [
  { id: 'requests', labelKey: 'connections.requests', path: '/me/follow-requests' },
  { id: 'followers', labelKey: 'connections.followers', path: '/me/followers' },
  { id: 'following', labelKey: 'connections.following', path: '/me/following' },
] as const

type TabId = (typeof TABS)[number]['id']

/** The owner's own lists only: the API serves `/me/...` and nothing here asks for anyone else's. */
export function ConnectionsPage() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<TabId>('requests')
  const baseId = useId()
  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      <h1 className="text-2xl font-extrabold">{t('connections.title')}</h1>
      <div role="tablist" className="grid grid-cols-3 gap-1 rounded-2xl bg-bg p-1">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`${baseId}-tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`${baseId}-panel`}
            onClick={() => setTab(item.id)}
            className={`min-h-11 rounded-xl px-2 text-sm font-semibold ${
              tab === item.id ? 'bg-surface text-accent shadow-sm' : 'text-muted hover:text-ink'
            }`}
          >
            {t(item.labelKey)}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`${baseId}-panel`} aria-labelledby={`${baseId}-tab-${tab}`}>
        <ConnectionsList key={tab} tab={tab} />
      </div>
    </section>
  )
}

function ConnectionsList({ tab }: { tab: TabId }) {
  const { t } = useTranslation()
  const api = useApi()
  const path = TABS.find((item) => item.id === tab)!.path
  const list = useQuery({
    queryKey: ['connections', tab],
    queryFn: ({ signal }) => api<{ users: UserCard[] }>(path, { signal }),
  })

  if (list.isError) {
    return (
      <p role="alert" className="text-sm font-medium text-danger">
        {t('common.error')}
      </p>
    )
  }
  if (!list.data) {
    return (
      <p role="status" className="text-muted">
        {t('auth.loading')}
      </p>
    )
  }
  if (list.data.users.length === 0) return <p className="text-muted">{t('connections.empty')}</p>
  return (
    <ul className="flex flex-col gap-2">
      {list.data.users.map((user) => (
        <UserCardRow
          key={user.username}
          user={user}
          actions={(nameId) =>
            tab === 'requests' ? (
              <RequestActions username={user.username} nameId={nameId} />
            ) : tab === 'followers' ? (
              <RemoveFollower username={user.username} nameId={nameId} />
            ) : (
              <FollowButton
                username={user.username}
                state={user.follow_state}
                nameId={nameId}
              />
            )
          }
        />
      ))}
    </ul>
  )
}
