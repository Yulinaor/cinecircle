import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

/**
 * Server state belongs to one signed-in user. Whenever the user id changes (sign-out, sign-in,
 * or a direct switch A -> B from another tab) in-flight requests are cancelled and the cache is
 * emptied. Returns false until that has happened for the current user, so callers render
 * nothing that could show, or fetch for, the previous user's data. Later tasks' queries are
 * covered automatically: this is the single place that resets them.
 */
export function useUserScopedCache(userId: string | null): boolean {
  const client = useQueryClient()
  const [scope, setScope] = useState<string | null | undefined>(undefined)
  useEffect(() => {
    if (scope === userId) return
    void client.cancelQueries()
    client.clear()
    // The cache is an external store we just reset; re-rendering is how callers learn it is ready.
    // oxlint-disable-next-line react/set-state-in-effect
    setScope(userId)
  }, [client, scope, userId])
  return scope === userId
}
