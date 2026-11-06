import type { Session } from '@supabase/supabase-js'
import { act, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { Me, MyProfile } from '../api/types'
import type { ApiCall } from '../api/useApi'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { PROFILE } from '../test/fakeMeApi'
import { renderApp } from '../test/renderApp'
import { AppShell } from './AppShell'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const sessionOf = (id: string) => ({ access_token: `token-${id}`, user: { id } }) as Session

function me(id: string, profile: Partial<MyProfile>): Me {
  return { id, email: null, profile: { ...PROFILE, ...profile } }
}

/**
 * GET /me answers are handed out by the test, one deferred promise per call; `calls` counts only
 * those. Every other endpoint (the header bell's, say) answers 404 and isn't counted.
 */
function deferredApi() {
  const pending: Array<(value: Me) => void> = []
  const calls = vi.fn()
  const fn = (path: string) => {
    if (path !== '/me') return Promise.reject(new ApiError(404, 'not_found'))
    calls()
    return new Promise<Me>((resolve) => pending.push(resolve))
  }
  return { api: fn as unknown as ApiCall, calls, resolve: (i: number, value: Me) => pending[i](value) }
}

describe('per-user query cache', () => {
  it('drops user A data when the session switches straight to user B', async () => {
    const fake = deferredApi()
    const view = renderApp(<AppShell />, { api: fake.api, route: '/settings', auth: { session: sessionOf('a') } })
    await waitFor(() => expect(fake.calls).toHaveBeenCalledTimes(1))
    await act(async () => fake.resolve(0, me('a', { display_name: 'Alice' })))
    expect(await screen.findByLabelText(he.settings.displayName)).toHaveValue('Alice')

    view.rerender(<AppShell />, { session: sessionOf('b') })
    await waitFor(() => expect(fake.calls).toHaveBeenCalledTimes(2))
    expect(screen.queryByDisplayValue('Alice')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(he.auth.loading)

    await act(async () => fake.resolve(1, me('b', { display_name: 'Bob' })))
    expect(await screen.findByLabelText(he.settings.displayName)).toHaveValue('Bob')
  })

  it('clears the cache on sign-out so the next sign-in fetches again', async () => {
    const fake = deferredApi()
    const view = renderApp(<AppShell />, { api: fake.api, auth: { session: sessionOf('a') } })
    await waitFor(() => expect(fake.calls).toHaveBeenCalledTimes(1))
    await act(async () => fake.resolve(0, me('a', {})))
    await screen.findByRole('navigation')

    view.rerender(<AppShell />, { status: 'signed_out', session: null })
    await screen.findByRole('heading', { name: he.auth.signIn })

    view.rerender(<AppShell />, { status: 'signed_in', session: sessionOf('a') })
    await waitFor(() => expect(fake.calls).toHaveBeenCalledTimes(2))
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('does not apply the language of a /me that resolves after sign-out', async () => {
    const fake = deferredApi()
    const view = renderApp(<AppShell />, { api: fake.api, auth: { session: sessionOf('a') } })
    await waitFor(() => expect(fake.calls).toHaveBeenCalledTimes(1))

    view.rerender(<AppShell />, { status: 'signed_out', session: null })
    await screen.findByRole('heading', { name: he.auth.signIn })

    await act(async () => fake.resolve(0, me('a', { locale: 'en' })))
    expect(document.documentElement.dir).toBe('rtl')
    expect(document.documentElement.lang).toBe('he')
  })
})
