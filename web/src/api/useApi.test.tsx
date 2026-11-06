import { renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthProvider'
import { ApiError } from './client'
import { useApi } from './useApi'

const mocks = vi.hoisted(() => ({ client: null as unknown }))

vi.mock('../auth/supabase', () => ({
  get supabase() {
    return mocks.client
  },
}))

const signOut = vi.fn(async () => {})

const wrapper = ({ children }: { children: ReactNode }) => (
  <AuthContext.Provider value={{ status: 'signed_in', session: null, signOut }}>
    {children}
  </AuthContext.Provider>
)

beforeEach(() => {
  signOut.mockClear()
  mocks.client = {
    auth: { getSession: async () => ({ data: { session: { access_token: 'fresh' } } }) },
  }
})
afterEach(() => vi.unstubAllGlobals())

describe('useApi', () => {
  it('sends the current access token', async () => {
    const fetchMock = vi.fn(async (..._args: unknown[]) => Response.json({ id: '1' }))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useApi(), { wrapper })
    await expect(result.current('/me')).resolves.toEqual({ id: '1' })
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer fresh')
  })

  it('signs out and rethrows on 401', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ detail: 'not_authenticated' }, { status: 401 })),
    )
    const { result } = renderHook(() => useApi(), { wrapper })
    const err = await result.current('/me').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(401)
    expect(signOut).toHaveBeenCalledTimes(1)
  })

  it('does not sign out on other errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ detail: 'not_found' }, { status: 404 })),
    )
    const { result } = renderHook(() => useApi(), { wrapper })
    await expect(result.current('/x')).rejects.toMatchObject({ status: 404, detail: 'not_found' })
    expect(signOut).not.toHaveBeenCalled()
  })

  it('rejects with not_authenticated and signs out when there is no session', async () => {
    mocks.client = { auth: { getSession: async () => ({ data: { session: null } }) } }
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useApi(), { wrapper })
    await expect(result.current('/me')).rejects.toMatchObject({
      status: 401,
      detail: 'not_authenticated',
    })
    expect(fetchMock).not.toHaveBeenCalled()
    expect(signOut).toHaveBeenCalled()
  })
})
