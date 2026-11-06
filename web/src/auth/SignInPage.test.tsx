import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { renderApp } from '../test/renderApp'
import { SignInPage } from './SignInPage'

const mocks = vi.hoisted(() => ({
  client: null as unknown,
}))

vi.mock('./supabase', () => ({
  get supabase() {
    return mocks.client
  },
}))

function fakeClient() {
  return {
    auth: {
      signInWithPassword: vi.fn(async (_creds: unknown) => ({ data: {}, error: null as unknown })),
      signUp: vi.fn(async (_creds: unknown) => ({
        data: { user: { identities: [{}] } as unknown, session: null as unknown },
        error: null as unknown,
      })),
      signInWithOAuth: vi.fn(async (_opts: unknown) => ({ data: {}, error: null as unknown })),
    },
  }
}

let client: ReturnType<typeof fakeClient>

beforeEach(async () => {
  initI18n()
  await setLocale('he')
  client = fakeClient()
  mocks.client = client
})

async function fill(email = 'a@b.co', password = 'secret123') {
  await userEvent.type(screen.getByLabelText(he.auth.email), email)
  await userEvent.type(screen.getByLabelText(he.auth.password), password)
}

describe('SignInPage', () => {
  it('signs in with email and password', async () => {
    renderApp(<SignInPage />)
    expect(screen.getByRole('heading', { name: he.auth.signIn })).toBeInTheDocument()
    await fill()
    await userEvent.click(screen.getByRole('button', { name: he.auth.signIn }))
    expect(client.auth.signInWithPassword).toHaveBeenCalledWith({
      email: 'a@b.co',
      password: 'secret123',
    })
  })

  it('shows check-your-email after sign-up', async () => {
    renderApp(<SignInPage />)
    await userEvent.click(screen.getByRole('button', { name: he.auth.switchToSignUp }))
    expect(screen.getByRole('heading', { name: he.auth.signUp })).toBeInTheDocument()
    await fill()
    await userEvent.click(screen.getByRole('button', { name: he.auth.signUp }))
    expect(client.auth.signUp).toHaveBeenCalledWith({ email: 'a@b.co', password: 'secret123' })
    expect(await screen.findByText(he.auth.checkEmail)).toBeInTheDocument()
  })

  it('reports an already registered email when sign-up returns no identities', async () => {
    client.auth.signUp.mockResolvedValueOnce({
      data: { user: { identities: [] }, session: null },
      error: null,
    })
    renderApp(<SignInPage />)
    await userEvent.click(screen.getByRole('button', { name: he.auth.switchToSignUp }))
    await fill()
    await userEvent.click(screen.getByRole('button', { name: he.auth.signUp }))
    expect(await screen.findByRole('alert')).toHaveTextContent(he.auth.errors.user_already_exists)
  })

  it.each(['invalid_credentials', 'email_not_confirmed', 'user_already_exists', 'weak_password'] as const)(
    'maps %s to a localised error',
    async (code) => {
      client.auth.signInWithPassword.mockResolvedValueOnce({ data: {}, error: { code } })
      renderApp(<SignInPage />)
      await fill()
      await userEvent.click(screen.getByRole('button', { name: he.auth.signIn }))
      expect(await screen.findByRole('alert')).toHaveTextContent(he.auth.errors[code])
    },
  )

  it('falls back to the generic error for unknown codes', async () => {
    client.auth.signInWithPassword.mockResolvedValueOnce({ data: {}, error: { code: 'weird' } })
    renderApp(<SignInPage />)
    await fill()
    await userEvent.click(screen.getByRole('button', { name: he.auth.signIn }))
    expect(await screen.findByRole('alert')).toHaveTextContent(he.auth.errors.generic)
  })

  it('starts Google sign-in with redirect back to the app', async () => {
    renderApp(<SignInPage />)
    await userEvent.click(screen.getByRole('button', { name: he.auth.google }))
    await waitFor(() =>
      expect(client.auth.signInWithOAuth).toHaveBeenCalledWith({
        provider: 'google',
        options: { redirectTo: window.location.origin },
      }),
    )
  })

  it('explains when auth is not configured', () => {
    mocks.client = null
    renderApp(<SignInPage />)
    expect(screen.getByText(he.auth.unconfigured)).toBeInTheDocument()
    expect(screen.queryByLabelText(he.auth.email)).not.toBeInTheDocument()
  })
})
