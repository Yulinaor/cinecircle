import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import tmdbLogo from '../assets/tmdb-logo.svg'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
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

  it('links to the taste quiz', async () => {
    renderApp(<SettingsPage />, { api: fakeMeApi().api })
    const link = await screen.findByRole('link', { name: he.settings.tasteQuiz })
    expect(link).toHaveAttribute('href', '/taste')
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

  it('Settings shows the TMDB notice and OMDb line', async () => {
    renderApp(<SettingsPage />, { api: fakeMeApi().api })
    expect(await screen.findByRole('heading', { name: he.about.heading })).toBeInTheDocument()
    expect(screen.getByText(he.about.tmdbNotice)).toBeInTheDocument()
    expect(screen.getByText(he.about.omdb)).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'TMDB' })
    expect(link).toHaveAttribute('href', 'https://www.themoviedb.org/')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link.className).toContain('min-h-11')
    // The official TMDB logo (TMDB's attribution page), not a home-made wordmark.
    const logo = within(link).getByRole('img', { name: 'TMDB' })
    expect(logo).toHaveAttribute('src', tmdbLogo)
  })

  it('shows the same notice in English', async () => {
    await setLocale('en')
    renderApp(<SettingsPage />, { api: fakeMeApi({ ...PROFILE, locale: 'en' }).api })
    expect(await screen.findByRole('heading', { name: en.about.heading })).toBeInTheDocument()
    expect(en.about.tmdbNotice).toBe(
      'This product uses the TMDB API but is not endorsed or certified by TMDB.',
    )
    expect(screen.getByText(en.about.tmdbNotice)).toBeInTheDocument()
    expect(screen.getByText(en.about.omdb)).toBeInTheDocument()
  })
})
