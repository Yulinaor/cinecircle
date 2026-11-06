import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { act } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthProvider'

const mocks = vi.hoisted(() => ({ client: null as unknown }))

vi.mock('./supabase', () => ({
  get supabase() {
    return mocks.client
  },
}))

type Listener = (event: string, session: unknown) => void
let listener: Listener
let unsubscribe: ReturnType<typeof vi.fn>
let getSession: ReturnType<typeof vi.fn>
let signOutFn: ReturnType<typeof vi.fn>

beforeEach(() => {
  unsubscribe = vi.fn()
  getSession = vi.fn(async () => ({ data: { session: null } }))
  signOutFn = vi.fn(async () => ({ error: null }))
  mocks.client = {
    auth: {
      getSession,
      signOut: signOutFn,
      onAuthStateChange: (cb: Listener) => {
        listener = cb
        return { data: { subscription: { unsubscribe } } }
      },
    },
  }
})

function Probe() {
  const { status, session, signOut } = useAuth()
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="token">{session?.access_token ?? ''}</span>
      <button onClick={() => void signOut()}>out</button>
      <button onClick={() => void signOut('local')}>out-local</button>
    </div>
  )
}

const renderProbe = () =>
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )

describe('AuthProvider', () => {
  it('starts loading, then signed_out with no session', async () => {
    renderProbe()
    expect(screen.getByTestId('status')).toHaveTextContent('loading')
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signed_out'))
  })

  it('is signed_in when a session exists', async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: 'tok' } } })
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signed_in'))
    expect(screen.getByTestId('token')).toHaveTextContent('tok')
  })

  it('follows auth state changes', async () => {
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signed_out'))
    act(() => listener('SIGNED_IN', { access_token: 'new' }))
    expect(screen.getByTestId('status')).toHaveTextContent('signed_in')
    act(() => listener('SIGNED_OUT', null))
    expect(screen.getByTestId('status')).toHaveTextContent('signed_out')
  })

  it('signOut calls supabase and ends the session', async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: 'tok' } } })
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signed_in'))
    await userEvent.click(screen.getByRole('button', { name: 'out' }))
    expect(signOutFn).toHaveBeenCalledWith({ scope: 'global' })
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signed_out'))
  })

  it('signOut("local") keeps the other devices signed in', async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: 'tok' } } })
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signed_in'))
    await userEvent.click(screen.getByRole('button', { name: 'out-local' }))
    expect(signOutFn).toHaveBeenCalledWith({ scope: 'local' })
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signed_out'))
  })

  it('ends the session even when supabase signOut rejects', async () => {
    getSession.mockResolvedValue({ data: { session: { access_token: 'tok' } } })
    signOutFn.mockRejectedValue(new Error('network down'))
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signed_in'))
    await userEvent.click(screen.getByRole('button', { name: 'out' }))
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signed_out'))
  })

  it('unsubscribes on unmount', async () => {
    const { unmount } = renderProbe()
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signed_out'))
    unmount()
    expect(unsubscribe).toHaveBeenCalled()
  })

  it('is signed_out when supabase is not configured', async () => {
    mocks.client = null
    renderProbe()
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signed_out'))
  })
})
