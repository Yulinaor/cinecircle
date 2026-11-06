import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { fakeMeApi } from '../test/fakeMeApi'
import { renderApp } from '../test/renderApp'
import { AppShell } from './AppShell'
import { LanguageToggle } from './LanguageToggle'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

describe('LanguageToggle', () => {
  it('language toggle saves the choice to the account', async () => {
    const fake = fakeMeApi()
    renderApp(<AppShell />, { api: fake.api })
    await screen.findByRole('navigation')
    await userEvent.click(screen.getByRole('button', { name: he.language.label }))
    expect(document.documentElement.dir).toBe('ltr')
    await vi.waitFor(() =>
      expect(fake.writes()).toEqual([['/me', { method: 'PATCH', body: { locale: 'en' } }]]),
    )
  })

  it('does not call the API when signed out', async () => {
    const fake = fakeMeApi()
    renderApp(<LanguageToggle />, { api: fake.api, auth: { status: 'signed_out', session: null } })
    await userEvent.click(screen.getByRole('button', { name: he.language.label }))
    expect(document.documentElement.dir).toBe('ltr')
    expect(fake.calls).not.toHaveBeenCalled()
  })

  it('does not PATCH before the profile exists', async () => {
    const fake = fakeMeApi(null)
    renderApp(<AppShell />, { api: fake.api })
    await screen.findByLabelText(he.onboarding.username)
    await userEvent.click(screen.getByRole('button', { name: he.language.label }))
    expect(document.documentElement.dir).toBe('ltr')
    expect(fake.writes()).toHaveLength(0)
  })

  it('still switches when saving to the account fails', async () => {
    const fake = fakeMeApi()
    fake.state.patchError = new ApiError(500, 'error')
    renderApp(<AppShell />, { api: fake.api })
    await screen.findByRole('navigation')
    await userEvent.click(screen.getByRole('button', { name: he.language.label }))
    expect(document.documentElement.dir).toBe('ltr')
    await vi.waitFor(() => expect(fake.writes()).toHaveLength(1))
    expect(screen.getByRole('navigation')).toBeInTheDocument()
  })
})
