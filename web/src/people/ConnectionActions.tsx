import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useApi } from '../api/useApi'
import { useActionName } from './actionName'

const SECONDARY =
  'min-h-11 rounded-xl border border-line bg-surface px-4 text-sm font-semibold text-ink hover:bg-bg disabled:opacity-60'
const PRIMARY = 'min-h-11 rounded-xl bg-accent px-4 text-sm font-semibold text-white disabled:opacity-60'

/** One request/follower change: runs it, then refetches everything it can have changed. */
function useConnectionChange(path: string, method: 'POST' | 'DELETE') {
  const api = useApi()
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<unknown>(path, { method }),
    onSettled: async () => {
      await Promise.all(
        (['connections', 'notifications', 'people'] as const).map((key) =>
          client.invalidateQueries({ queryKey: [key] }),
        ),
      )
    },
  })
}

function ErrorLine() {
  const { t } = useTranslation()
  return (
    <p role="alert" className="text-xs font-medium text-danger">
      {t('common.error')}
    </p>
  )
}

/**
 * Accept / Decline for a pending follow request (Connections page and inline in notifications).
 * `nameId` is the element naming the person; each button is named "<action> <person>".
 */
export function RequestActions({ username, nameId }: { username: string; nameId?: string }) {
  const { t } = useTranslation()
  const base = `/follow-requests/${encodeURIComponent(username)}`
  const accept = useConnectionChange(`${base}/accept`, 'POST')
  const decline = useConnectionChange(base, 'DELETE')
  const busy = accept.isPending || decline.isPending
  const acceptName = useActionName(nameId)
  const declineName = useActionName(nameId)
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        <button
          type="button"
          {...acceptName}
          disabled={busy}
          onClick={() => accept.mutate()}
          className={PRIMARY}
        >
          {t('connections.accept')}
        </button>
        <button
          type="button"
          {...declineName}
          disabled={busy}
          onClick={() => decline.mutate()}
          className={SECONDARY}
        >
          {t('connections.decline')}
        </button>
      </div>
      {(accept.isError || decline.isError) && <ErrorLine />}
    </div>
  )
}

/** Removes one of your followers. */
export function RemoveFollower({ username, nameId }: { username: string; nameId?: string }) {
  const { t } = useTranslation()
  const remove = useConnectionChange(`/followers/${encodeURIComponent(username)}`, 'DELETE')
  const removeName = useActionName(nameId)
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        {...removeName}
        disabled={remove.isPending}
        onClick={() => remove.mutate()}
        className={SECONDARY}
      >
        {t('connections.remove')}
      </button>
      {remove.isError && <ErrorLine />}
    </div>
  )
}
