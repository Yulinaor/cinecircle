import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { Session } from '@supabase/supabase-js'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import { ApiOverrideContext, type ApiCall } from '../api/useApi'
import { AuthContext, type AuthState } from '../auth/AuthProvider'

export const FAKE_SESSION = { access_token: 'test-token', user: { id: 'user-1' } } as Session

export type RenderAppOptions = {
  auth?: Partial<AuthState>
  api?: ApiCall
  route?: string
}

/** Wraps `ui` in a query client (no retries), a fake auth context, an optional fake API and a router. */
export function renderApp(ui: ReactElement, { auth, api, route = '/' }: RenderAppOptions = {}) {
  const value: AuthState = {
    status: 'signed_in',
    session: FAKE_SESSION,
    signOut: vi.fn(async () => {}),
    ...auth,
  }
  let current = value
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrap = (children: ReactNode) => (
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={current}>
        <ApiOverrideContext.Provider value={api ?? null}>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </ApiOverrideContext.Provider>
      </AuthContext.Provider>
    </QueryClientProvider>
  )
  const result = render(wrap(ui))
  return {
    ...result,
    auth: value,
    /** Optionally swaps the auth state (e.g. another user, or signed out) for the re-render. */
    rerender: (next: ReactElement, nextAuth?: Partial<AuthState>) => {
      if (nextAuth) current = { ...value, ...nextAuth }
      result.rerender(wrap(next))
    },
  }
}
