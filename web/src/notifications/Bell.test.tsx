import { act, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { fakeApi } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { Bell } from './Bell'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

afterEach(() => {
  vi.useRealTimers()
})

const bell = (unread: number) => he.notifications.bell.replace('{{unread}}', String(unread))

describe('Bell', () => {
  it('bell shows the unread count and hides at zero', async () => {
    const fake = fakeApi({ 'GET /notifications': { items: [], unread_count: 3 } })
    renderApp(<Bell />, { api: fake.api })
    const link = await screen.findByRole('link', { name: bell(3) })
    expect(link).toHaveAttribute('href', '/notifications')
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('hides the badge when there is nothing unread', async () => {
    const fake = fakeApi({ 'GET /notifications': { items: [], unread_count: 0 } })
    renderApp(<Bell />, { api: fake.api })
    const link = await screen.findByRole('link', { name: bell(0) })
    expect(link).toHaveTextContent('')
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('has no badge before the count is known', () => {
    renderApp(<Bell />, { api: fakeApi({}).api })
    expect(screen.getByRole('link', { name: bell(0) })).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('caps the badge at 99+', async () => {
    const fake = fakeApi({ 'GET /notifications': { items: [], unread_count: 100 } })
    renderApp(<Bell />, { api: fake.api })
    expect(await screen.findByText('99+')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: bell(100).replace('100', '99+') })).toBeInTheDocument()
  })

  it('shows 99 as is', async () => {
    const fake = fakeApi({ 'GET /notifications': { items: [], unread_count: 99 } })
    renderApp(<Bell />, { api: fake.api })
    expect(await screen.findByText('99')).toBeInTheDocument()
  })

  it('names the link in English', async () => {
    await setLocale('en')
    const fake = fakeApi({ 'GET /notifications': { items: [], unread_count: 2 } })
    renderApp(<Bell />, { api: fake.api })
    expect(
      await screen.findByRole('link', { name: en.notifications.bell.replace('{{unread}}', '2') }),
    ).toBeInTheDocument()
  })

  it('polls every 60 seconds', async () => {
    vi.useFakeTimers()
    const fake = fakeApi({ 'GET /notifications': { items: [], unread_count: 1 } })
    renderApp(<Bell />, { api: fake.api })
    await act(() => vi.advanceTimersByTimeAsync(0))
    expect(fake.count('GET /notifications')).toBe(1)
    await act(() => vi.advanceTimersByTimeAsync(59_000))
    expect(fake.count('GET /notifications')).toBe(1)
    await act(() => vi.advanceTimersByTimeAsync(1_000))
    expect(fake.count('GET /notifications')).toBe(2)
    await act(() => vi.advanceTimersByTimeAsync(60_000))
    expect(fake.count('GET /notifications')).toBe(3)
  })

  it('refetches when the window regains focus', async () => {
    const fake = fakeApi({ 'GET /notifications': { items: [], unread_count: 1 } })
    renderApp(<Bell />, { api: fake.api })
    await screen.findByText('1')
    expect(fake.count('GET /notifications')).toBe(1)
    act(() => {
      window.dispatchEvent(new Event('visibilitychange'))
    })
    await vi.waitFor(() => expect(fake.count('GET /notifications')).toBe(2))
  })
})
