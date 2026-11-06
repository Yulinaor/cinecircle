import { vi } from 'vitest'
import { ApiError } from '../api/client'
import type { ApiCall } from '../api/useApi'

type Init = { method?: string; body?: unknown } | undefined
export type FakeRoute = unknown | ((init: Init, path: string) => unknown)

/**
 * A fake network keyed by `"METHOD /path"` (query string included). A route is either a value or a
 * function returning one (it may throw an ApiError or return a promise). Unknown routes answer 404.
 */
export function fakeApi(routes: Record<string, FakeRoute>) {
  const fn = vi.fn(async (path: string, init?: Init): Promise<unknown> => {
    const route = routes[`${init?.method ?? 'GET'} ${path}`]
    if (route === undefined) throw new ApiError(404, 'not_found')
    return typeof route === 'function' ? (route as (i: Init, p: string) => unknown)(init, path) : route
  })
  const keyOf = ([path, init]: [string, Init]) => `${init?.method ?? 'GET'} ${path}`
  return {
    api: fn as unknown as ApiCall,
    calls: fn,
    /** `"METHOD /path"` of every call so far, in order. */
    log: () => fn.mock.calls.map((c) => keyOf(c as [string, Init])),
    /** Number of calls to exactly this `"METHOD /path"`. */
    count: (key: string) => fn.mock.calls.filter((c) => keyOf(c as [string, Init]) === key).length,
  }
}

export const DANA = {
  username: 'dana',
  display_name: 'Dana',
  avatar_url: null,
  follow_state: 'none',
} as const
