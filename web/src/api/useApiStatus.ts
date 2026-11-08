import { useEffect, useState } from 'react'
import { getHealth, type HealthResponse } from './client'

export type ApiStatus = 'checking' | 'connected' | 'waking' | 'offline'

/** No answer after this long: the free server is probably waking up. */
export const WAKING_AFTER_MS = 3000
/** No answer after this long: give up on this attempt. A free-tier cold start can take over a minute. */
export const OFFLINE_AFTER_MS = 90000
/** While offline, try again this often. */
export const RETRY_EVERY_MS = 15000
/** While connected, check again this often so the header notices when the server stops. */
export const RECHECK_EVERY_MS = 60000

export function useApiStatus(
  fetchHealth: (signal?: AbortSignal) => Promise<HealthResponse> = getHealth,
): ApiStatus {
  const [status, setStatus] = useState<ApiStatus>('checking')

  useEffect(() => {
    let cancelled = false
    let controller: AbortController | undefined
    const timers = new Set<ReturnType<typeof setTimeout>>()
    const later = (fn: () => void, ms: number) => {
      const id = setTimeout(() => {
        timers.delete(id)
        fn()
      }, ms)
      timers.add(id)
      return id
    }

    const attempt = () => {
      const current = new AbortController()
      controller = current
      let settled = false
      const settle = () => {
        settled = true
        clearTimeout(waking)
        clearTimeout(giveUp)
        timers.delete(waking)
        timers.delete(giveUp)
      }
      const fail = () => {
        setStatus('offline')
        later(attempt, RETRY_EVERY_MS)
      }

      // A retry while offline keeps showing "offline" until it succeeds.
      const waking = later(() => setStatus((s) => (s === 'offline' ? s : 'waking')), WAKING_AFTER_MS)
      const giveUp = later(() => {
        if (settled) return
        settle()
        current.abort()
        fail()
      }, OFFLINE_AFTER_MS)

      fetchHealth(current.signal).then(
        () => {
          if (settled || cancelled) return
          settle()
          setStatus('connected')
          later(attempt, RECHECK_EVERY_MS)
        },
        () => {
          if (settled || cancelled) return
          settle()
          fail()
        },
      )
    }

    attempt()
    return () => {
      cancelled = true
      timers.forEach(clearTimeout)
      timers.clear()
      controller?.abort()
    }
  }, [fetchHealth])

  return status
}
