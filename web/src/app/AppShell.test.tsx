import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { initI18n, LOCALE_STORAGE_KEY, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { renderApp, type RenderAppOptions } from '../test/renderApp'
import type { ApiCall } from '../api/useApi'
import { fakeMeApi } from '../test/fakeMeApi'
import { findPhysicalUtilities } from '../test/rtl'
import { AppShell } from './AppShell'

vi.mock('../auth/supabase', () => ({ supabase: null }))

function renderShell(options?: RenderAppOptions) {
  return renderApp(<AppShell />, { api: fakeMeApi().api, ...options })
}

async function navTexts() {
  const nav = await screen.findByRole('navigation')
  return within(nav)
    .getAllByRole('link')
    .map((a) => a.textContent)
}

describe('AppShell', () => {
  beforeEach(async () => {
    localStorage.clear()
    initI18n()
    await setLocale('he')
    localStorage.clear()
  })

  it('renders Hebrew RTL by default with 5 tabs in order', async () => {
    renderShell()
    expect(await navTexts()).toEqual(['בית', 'גלו', 'פרסום', 'רשימת צפייה', 'פרופיל'])
    expect(document.documentElement.dir).toBe('rtl')
    expect(screen.getByRole('link', { name: 'בית' })).toHaveAttribute('aria-current', 'page')
  })

  it('shows the app shell when signed in', async () => {
    renderShell({ auth: { status: 'signed_in' } })
    expect(within(await screen.findByRole('navigation')).getAllByRole('link')).toHaveLength(5)
  })

  it('waits for the account before showing the app', async () => {
    renderShell()
    expect(screen.getByRole('status')).toHaveTextContent(he.auth.loading)
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    await screen.findByRole('navigation')
  })

  it('offers a retry when the account cannot be loaded', async () => {
    const fake = fakeMeApi()
    const original = fake.calls.getMockImplementation()!
    fake.calls.mockImplementationOnce(async () => {
      throw new ApiError(500, 'error')
    })
    fake.calls.mockImplementation(original)
    renderShell({ api: fake.api })
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    await userEvent.click(screen.getByRole('button', { name: he.common.retry }))
    expect(await screen.findByRole('navigation')).toBeInTheDocument()
  })

  it('links to settings from the header', async () => {
    renderShell()
    await userEvent.click(await screen.findByRole('link', { name: he.settings.title }))
    expect(await screen.findByRole('heading', { name: he.settings.title })).toBeInTheDocument()
  })

  it('shows the notifications bell with the unread count in the header', async () => {
    const me = fakeMeApi().api
    const api = (async (path: string, init?: Parameters<ApiCall>[1]) =>
      path === '/notifications' ? { items: [], unread_count: 4 } : me(path, init)) as ApiCall
    renderShell({ api })
    const bell = await screen.findByRole('link', {
      name: he.notifications.bell.replace('{{unread}}', '4'),
    })
    expect(bell).toHaveAttribute('href', '/notifications')
    expect(within(screen.getByRole('navigation')).queryByRole('link', { name: /התראות/ })).toBeNull()
  })

  it('has no bell before the account has a profile', async () => {
    renderShell({ api: fakeMeApi(null).api })
    await screen.findByRole('heading', { name: he.onboarding.title })
    expect(screen.queryByRole('link', { name: /התראות/ })).not.toBeInTheDocument()
  })

  it('the profile tab links to connections, people and settings', async () => {
    renderShell({ route: '/profile' })
    expect(await screen.findByRole('link', { name: he.connections.title })).toHaveAttribute(
      'href',
      '/connections',
    )
    expect(screen.getByRole('link', { name: he.people.title })).toHaveAttribute('href', '/people')
    const settings = screen.getAllByRole('link', { name: he.settings.title })
    expect(settings.map((a) => a.getAttribute('href'))).toEqual(['/settings', '/settings'])
  })

  it('keeps accessible names on the icon-only header controls', async () => {
    renderShell()
    const header = await screen.findByRole('banner')
    expect(
      await within(header).findByRole('link', {
        name: he.notifications.bell.replace('{{unread}}', '0'),
      }),
    ).toBeInTheDocument()
    expect(within(header).getByRole('link', { name: he.settings.title })).toHaveAttribute(
      'href',
      '/settings',
    )
    expect(within(header).getByRole('button', { name: 'שינוי שפה' })).toBeInTheDocument()
    // Sign out lives on the settings page once there is a profile, not in the header.
    expect(within(header).queryByRole('button', { name: he.auth.signOut })).not.toBeInTheDocument()
  })

  it('signs out from the header while there is no profile yet', async () => {
    const { auth } = renderShell({ api: fakeMeApi(null).api })
    await screen.findByRole('heading', { name: he.onboarding.title })
    await userEvent.click(
      within(screen.getByRole('banner')).getByRole('button', { name: he.auth.signOut }),
    )
    expect(auth.signOut).toHaveBeenCalled()
  })

  it('shows the sign-in page when signed out', () => {
    renderShell({ auth: { status: 'signed_out', session: null } })
    expect(screen.getByRole('heading', { name: he.auth.signIn })).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'שינוי שפה' })).toBeInTheDocument()
  })

  it('shows a loading status while the session is restored', () => {
    renderShell({ auth: { status: 'loading', session: null } })
    expect(screen.getByRole('status')).toHaveTextContent(he.auth.loading)
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('switches to English LTR from the toggle and remembers it', async () => {
    renderShell()
    await screen.findByRole('navigation')
    const toggle = screen.getByRole('button', { name: 'שינוי שפה' })
    expect(toggle).toHaveTextContent('English')
    await userEvent.click(toggle)
    expect(document.documentElement.dir).toBe('ltr')
    expect(await navTexts()).toEqual(['Home', 'Discover', 'Post', 'Wishlist', 'Profile'])
    expect(screen.getByRole('button', { name: 'Change language' })).toHaveTextContent('עברית')
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('en')
  })

  it('source never uses physical left/right utilities', () => {
    const sources = import.meta.glob<string>(
      ['../**/*.{ts,tsx,css}', '../../index.html', '!../**/*.test.*', '!../test/**'],
      { query: '?raw', import: 'default', eager: true },
    )
    const files = Object.keys(sources)
    expect(files).toEqual(expect.arrayContaining(['../theme/tokens.css', '../../index.html']))
    const offenders = files.flatMap((f) =>
      findPhysicalUtilities(sources[f]).map((cls) => `${f}: ${cls}`),
    )
    expect(offenders).toEqual([])
  })
})
