import { useId, type ReactNode } from 'react'
import { Link } from 'react-router'
import type { UserCard } from '../api/types'
import { Avatar } from './Avatar'
import { FollowButton } from './FollowButton'

/**
 * One person in a list: avatar, name, @username, then the actions. Without `actions`, a follow
 * control. Actions are linked to the name so identical buttons in a list stay distinguishable.
 */
export function UserCardRow({
  user,
  actions,
}: {
  user: UserCard
  actions?: (nameId: string) => ReactNode
}) {
  const nameId = useId()
  return (
    <li className="flex items-center gap-3 rounded-2xl border border-line bg-surface p-3">
      <Avatar url={user.avatar_url} name={user.display_name} />
      <div className="min-w-0 flex-1">
        <p id={nameId} className="truncate font-semibold text-ink">
          <Link to={`/u/${user.username}`} className="hover:underline">
            {user.display_name}
          </Link>
        </p>
        <p className="truncate text-sm text-muted">
          <bdi>@{user.username}</bdi>
        </p>
      </div>
      {actions ? (
        actions(nameId)
      ) : (
        <FollowButton username={user.username} state={user.follow_state} nameId={nameId} />
      )}
    </li>
  )
}
