import { vi } from 'vitest'
import { ApiError } from '../api/client'
import type { Me, MyProfile } from '../api/types'
import type { ApiCall } from '../api/useApi'

export const PROFILE: MyProfile = {
  username: 'gal_b',
  display_name: 'Gal',
  avatar_url: null,
  bio: null,
  locale: 'he',
}

type Call = [path: string, init?: { method?: string; body?: unknown }]

/** In-memory `/me` endpoints (GET, POST, PATCH). Set `state.postError` to make POST fail. */
export function fakeMeApi(profile: MyProfile | null = PROFILE) {
  let me: Me = { id: 'user-1', email: 'a@b.co', profile, taste_unlocked: profile !== null }
  const state = { postError: null as ApiError | null, patchError: null as ApiError | null }
  const fn = vi.fn(async (...[path, init]: Call): Promise<unknown> => {
    const method = init?.method ?? 'GET'
    const body = (init?.body ?? {}) as Record<string, unknown>
    if (path !== '/me') throw new ApiError(404, 'not_found')
    if (method === 'GET') return me
    if (method === 'POST') {
      if (state.postError) throw state.postError
      me = {
        ...me,
        profile: {
          username: body.username as string,
          display_name: body.display_name as string,
          avatar_url: null,
          bio: null,
          locale: body.locale as 'he' | 'en',
        },
      }
      return me
    }
    if (state.patchError) throw state.patchError
    if (!me.profile) throw new ApiError(409, 'profile_required')
    me = { ...me, profile: { ...me.profile, ...body } as MyProfile }
    return me
  })
  return {
    api: fn as unknown as ApiCall,
    calls: fn,
    state,
    /** Calls other than GET /me. */
    writes: () => fn.mock.calls.filter(([, init]) => init?.method && init.method !== 'GET'),
  }
}
