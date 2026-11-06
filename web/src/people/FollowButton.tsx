import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { FollowState } from '../api/types'
import { useApi } from '../api/useApi'

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
  describedBy,
}: {
  username: string
  state: FollowState
  /** Id of the element naming the person, so identical buttons in a list are told apart. */
  describedBy?: string
}) {
  const { t } = useTranslation()
  const api = useApi()
  const client = useQueryClient()
  // Applies only while the server state it was made from is still what the parent shows;
  // once a refetch changes `state`, the server's answer wins.
  const [local, setLocal] = useState<{ from: FollowState; value: Target } | null>(null)
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
    onMutate: () => setLocal({ from: state, value: state === 'none' ? 'requested' : 'none' }),
    onSuccess: (value) => setLocal({ from: state, value }),
    onError: () => setLocal(null),
    onSettled: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['people'] }),
        client.invalidateQueries({ queryKey: ['connections'] }),
      ])
    },
  })

  if (state === 'self') return null
  const shown: Target = local && local.from === state ? local.value : state
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        disabled={change.isPending}
        aria-describedby={describedBy}
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
