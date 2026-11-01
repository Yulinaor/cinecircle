import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'
import { initI18n, LOCALE_STORAGE_KEY, setLocale } from '../i18n'
import { AppShell } from './AppShell'

function renderShell() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <AppShell />
    </MemoryRouter>,
  )
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
    const sources = import.meta.glob<string>(['../**/*.tsx', '!../**/*.test.tsx'], {
      query: '?raw',
      import: 'default',
      eager: true,
    })
    const files = Object.keys(sources)
    expect(files.length).toBeGreaterThan(0)
    const offenders = files.filter((f) =>
      /\b(ml|mr|pl|pr|left|right)-\d|text-(left|right)\b/.test(sources[f]),
    )
    expect(offenders).toEqual([])
  })
})
