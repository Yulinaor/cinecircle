import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { FollowState } from '../api/types'
import { useApi } from '../api/useApi'
import { useActionName } from './actionName'

const LABEL_KEY = {
  none: 'follow.follow',
  requested: 'follow.requested',
  following: 'follow.following',
} as const

type Target = Exclude<FollowState, 'self'>

/**
 * Follow / Requested / Following for another person. The label changes the moment you press it
 * (and the button is disabled while the request is on its way); a failure puts the old label back.
 * Renders nothing for yourself.
 */
export function FollowButton({
  username,
  state,
  nameId,
}: {
  username: string
  state: FollowState
  /** Id of the element naming the person: the button is then named "<label> <person>". */
  nameId?: string
}) {
  const { t } = useTranslation()
  const api = useApi()
  const client = useQueryClient()
  // What the button shows until the parent hands us a new server state; then the server wins.
  const [local, setLocal] = useState<Target | null>(null)
  const [seenState, setSeenState] = useState(state)
  if (seenState !== state) {
    // Adjusted during render (not in an effect), so a stale value never paints, and it can't
    // come back later when the server state returns to what it was.
    setSeenState(state)
    setLocal(null)
  }
  const actionName = useActionName(nameId)
  const path = `/follows/${encodeURIComponent(username)}`

  const change = useMutation({
    mutationFn: async (): Promise<Target> => {
      if (state === 'none') {
        const answer = await api<{ follow_state: Target }>(path, { method: 'POST' })
        return answer.follow_state
      }
      await api<void>(path, { method: 'DELETE' })
      return 'none'
    },
    onMutate: () => setLocal(state === 'none' ? 'requested' : 'none'),
    onSuccess: (value) => setLocal(value),
    onError: () => setLocal(null),
    onSettled: async () => {
      // Whose posts you can see changed: Home, profile posts and title pages refetch in the
      // background (not awaited, so the button is usable again without waiting for them).
      void client.invalidateQueries({ queryKey: ['posts'] })
      void client.invalidateQueries({ queryKey: ['title'] })
      // "via <person>" on the wishlist shows only while you can see that person's post.
      void client.invalidateQueries({ queryKey: ['wishlist'] })
      await Promise.all([
        client.invalidateQueries({ queryKey: ['people'] }),
        client.invalidateQueries({ queryKey: ['connections'] }),
        client.invalidateQueries({ queryKey: ['profile'] }),
      ])
    },
  })

  if (state === 'self') return null
  const shown: Target = local ?? state
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        disabled={change.isPending}
        {...actionName}
        onClick={() => change.mutate()}
        className={`min-h-11 rounded-xl px-4 text-sm font-semibold disabled:opacity-60 ${
          shown === 'none'
            ? 'bg-accent text-white'
            : 'border border-line bg-surface text-ink hover:bg-bg'
        }`}
      >
        {t(LABEL_KEY[shown])}
      </button>
      {change.isError && (
        <p role="alert" className="text-xs font-medium text-danger">
          {t('common.error')}
        </p>
      )}
    </div>
  )
}
