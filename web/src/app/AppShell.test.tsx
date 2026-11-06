import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { initI18n, LOCALE_STORAGE_KEY, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { renderApp, type RenderAppOptions } from '../test/renderApp'
import { findPhysicalUtilities } from '../test/rtl'
import { AppShell } from './AppShell'

vi.mock('../auth/supabase', () => ({ supabase: null }))

function renderShell(options?: RenderAppOptions) {
  return renderApp(<AppShell />, options)
}

function navTexts() {
  const nav = screen.getByRole('navigation')
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

  it('renders Hebrew RTL by default with 5 tabs in order', () => {
    renderShell()
    expect(document.documentElement.dir).toBe('rtl')
    expect(navTexts()).toEqual(['בית', 'גלו', 'פרסום', 'רשימת צפייה', 'פרופיל'])
    expect(screen.getByRole('link', { name: 'בית' })).toHaveAttribute('aria-current', 'page')
  })

  it('shows the app shell when signed in', () => {
    renderShell({ auth: { status: 'signed_in' } })
    expect(within(screen.getByRole('navigation')).getAllByRole('link')).toHaveLength(5)
  })

  it('signs out from the header', async () => {
    const { auth } = renderShell()
    await userEvent.click(screen.getByRole('button', { name: he.auth.signOut }))
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
    const toggle = screen.getByRole('button', { name: 'שינוי שפה' })
    expect(toggle).toHaveTextContent('English')
    await userEvent.click(toggle)
    expect(document.documentElement.dir).toBe('ltr')
    expect(navTexts()).toEqual(['Home', 'Discover', 'Post', 'Wishlist', 'Profile'])
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
