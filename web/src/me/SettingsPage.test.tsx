import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { fakeMeApi, PROFILE } from '../test/fakeMeApi'
import { renderApp } from '../test/renderApp'
import { SettingsPage } from './SettingsPage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

describe('SettingsPage', () => {
  it('shows the current profile values and a bio counter', async () => {
    const fake = fakeMeApi({ ...PROFILE, bio: 'abc' })
    renderApp(<SettingsPage />, { api: fake.api })
    expect(await screen.findByLabelText(he.settings.displayName)).toHaveValue('Gal')
    expect(screen.getByLabelText(he.settings.bio)).toHaveValue('abc')
    expect(screen.getByText('3/300')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: he.settings.save })).toBeDisabled()
  })

  it('settings saves bio and signs out', async () => {
    const fake = fakeMeApi()
    const { auth } = renderApp(<SettingsPage />, { api: fake.api })
    await userEvent.type(await screen.findByLabelText(he.settings.bio), 'hi')
    expect(screen.getByText('2/300')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: he.settings.save }))
    expect(await screen.findByRole('status')).toHaveTextContent(he.settings.saved)
    expect(fake.writes()).toEqual([['/me', { method: 'PATCH', body: { bio: 'hi' } }]])
    await userEvent.click(screen.getByRole('button', { name: he.auth.signOut }))
    expect(auth.signOut).toHaveBeenCalled()
  })

  it('caps the bio at 300 characters', async () => {
    renderApp(<SettingsPage />, { api: fakeMeApi().api })
    expect(await screen.findByLabelText(he.settings.bio)).toHaveAttribute('maxlength', '300')
  })

  it('saves the language to the account', async () => {
    const fake = fakeMeApi()
    renderApp(<SettingsPage />, { api: fake.api })
    const group = await screen.findByRole('group', { name: he.settings.language })
    await userEvent.click(within(group).getByRole('button', { name: 'English' }))
    expect(document.documentElement.dir).toBe('ltr')
    await vi.waitFor(() =>
      expect(fake.writes()).toEqual([['/me', { method: 'PATCH', body: { locale: 'en' } }]]),
    )
  })

  it('shows an error when saving fails', async () => {
    const fake = fakeMeApi()
    fake.state.patchError = new ApiError(500, 'error')
    renderApp(<SettingsPage />, { api: fake.api })
    await userEvent.type(await screen.findByLabelText(he.settings.bio), 'hi')
    await userEvent.click(screen.getByRole('button', { name: he.settings.save }))
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
  })
})
