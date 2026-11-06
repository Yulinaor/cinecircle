import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Session } from '@supabase/supabase-js'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { AppShell } from '../app/AppShell'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { fakeMeApi, PROFILE } from '../test/fakeMeApi'
import { FAKE_SESSION, renderApp } from '../test/renderApp'

// delay: null skips the per-keystroke setTimeout(0), which is slow under parallel load.
const typist = userEvent.setup({ delay: null })

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

async function fillAndSubmit(username: string, displayName = 'Gal') {
  await typist.type(await screen.findByLabelText(he.onboarding.username), username)
  const name = screen.getByLabelText(he.onboarding.displayName)
  await userEvent.clear(name)
  await typist.type(name, displayName)
  await userEvent.click(screen.getByRole('button', { name: he.onboarding.submit }))
}

describe('onboarding', () => {
  it('shows onboarding when the profile is missing', async () => {
    const { api } = fakeMeApi(null)
    renderApp(<AppShell />, { api })
    expect(await screen.findByRole('heading', { name: he.onboarding.title })).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('validates the username before sending', async () => {
    const fake = fakeMeApi(null)
    renderApp(<AppShell />, { api: fake.api })
    await fillAndSubmit('a!')
    expect(await screen.findByRole('alert')).toHaveTextContent(he.onboarding.usernameHint)
    expect(fake.writes()).toHaveLength(0)
  })

  it('creates the profile and enters the app', async () => {
    const fake = fakeMeApi(null)
    renderApp(<AppShell />, { api: fake.api })
    await fillAndSubmit('gal_b')
    expect(await screen.findByRole('navigation')).toBeInTheDocument()
    expect(within(screen.getByRole('navigation')).getAllByRole('link')).toHaveLength(5)
    expect(fake.writes()).toEqual([
      ['/me', { method: 'POST', body: { username: 'gal_b', display_name: 'Gal', locale: 'he' } }],
    ])
  })

  it('trims and lower-cases the username before sending', async () => {
    const fake = fakeMeApi(null)
    renderApp(<AppShell />, { api: fake.api })
    await fillAndSubmit('  Gal_B ')
    await screen.findByRole('navigation')
    expect(fake.writes()[0][1]).toMatchObject({ body: { username: 'gal_b' } })
  })

  it('shows username taken and keeps the form', async () => {
    const fake = fakeMeApi(null)
    fake.state.postError = new ApiError(409, 'username_taken')
    renderApp(<AppShell />, { api: fake.api })
    await fillAndSubmit('gal_b')
    expect(await screen.findByRole('alert')).toHaveTextContent(he.onboarding.errors.username_taken)
    expect(screen.getByLabelText(he.onboarding.username)).toHaveValue('gal_b')
    expect(screen.getByLabelText(he.onboarding.displayName)).toHaveValue('Gal')
  })

  it.each(['username_reserved', 'username_invalid'] as const)(
    'maps %s to a localised error',
    async (code) => {
      const fake = fakeMeApi(null)
      fake.state.postError = new ApiError(422, code)
      renderApp(<AppShell />, { api: fake.api })
      await fillAndSubmit('gal_b')
      expect(await screen.findByRole('alert')).toHaveTextContent(he.onboarding.errors[code])
    },
  )

  it('falls back to a generic error for other failures', async () => {
    const fake = fakeMeApi(null)
    fake.state.postError = new ApiError(500, 'error')
    renderApp(<AppShell />, { api: fake.api })
    await fillAndSubmit('gal_b')
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
  })

  it('prefills the display name from the Google profile', async () => {
    const session = {
      ...FAKE_SESSION,
      user: { id: 'user-1', user_metadata: { full_name: 'Gal Ben' } },
    } as unknown as Session
    renderApp(<AppShell />, { api: fakeMeApi(null).api, auth: { session } })
    expect(await screen.findByLabelText(he.onboarding.displayName)).toHaveValue('Gal Ben')
  })

  it('sends the chosen language', async () => {
    const fake = fakeMeApi(null)
    renderApp(<AppShell />, { api: fake.api })
    const group = await screen.findByRole('group', { name: he.onboarding.language })
    await userEvent.click(within(group).getByRole('button', { name: 'English' }))
    expect(document.documentElement.dir).toBe('ltr')
    await typist.type(screen.getByLabelText(en.onboarding.username), 'gal_b')
    await typist.type(screen.getByLabelText(en.onboarding.displayName), 'Gal')
    await userEvent.click(screen.getByRole('button', { name: en.onboarding.submit }))
    await screen.findByRole('navigation')
    expect(fake.writes()[0][1]).toMatchObject({ body: { locale: 'en' } })
  })
})

describe('account language', () => {
  it('applies the account language on sign-in', async () => {
    const { api } = fakeMeApi({ ...PROFILE, locale: 'en' })
    renderApp(<AppShell />, { api })
    expect(await screen.findByRole('link', { name: en.nav.home })).toBeInTheDocument()
    expect(document.documentElement.dir).toBe('ltr')
  })
})
