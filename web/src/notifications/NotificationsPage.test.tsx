import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { NotificationItem } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { DANA, fakeApi } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { Bell } from './Bell'
import { NotificationsPage } from './NotificationsPage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const ERAN = { ...DANA, username: 'eran', display_name: 'Eran' }

const request = (over: Partial<NotificationItem> = {}): NotificationItem => ({
  id: 1,
  type: 'follow_request',
  actor: DANA,
  created_at: '2026-11-06T10:00:00Z',
  read: false,
  request_pending: true,
  ...over,
})

function notifications(items: NotificationItem[]) {
  const state = { items }
  const fake = fakeApi({
    'GET /notifications': () => ({
      items: state.items,
      unread_count: state.items.filter((i) => !i.read).length,
      next_cursor: null,
    }),
    'POST /notifications/read': () => {
      state.items = state.items.map((i) => ({ ...i, read: true }))
    },
    'POST /follow-requests/dana/accept': () => {
      state.items = state.items.map((i) => ({ ...i, request_pending: false }))
      return DANA
    },
    'DELETE /follow-requests/dana': () => {
      state.items = state.items.map((i) => ({ ...i, request_pending: false }))
    },
  })
  return { ...fake, state }
}

const bell = (unread: number) => he.notifications.bell.replace('{{unread}}', String(unread))

describe('NotificationsPage', () => {
  it('opening notifications marks them read', async () => {
    const fake = notifications([request(), request({ id: 2, type: 'follow_accepted', request_pending: false })])
    renderApp(
      <>
        <Bell />
        <NotificationsPage />
      </>,
      { api: fake.api },
    )
    await vi.waitFor(() => expect(fake.count('POST /notifications/read')).toBe(1))
    expect(await screen.findByRole('link', { name: bell(0) })).toBeInTheDocument()
    expect(screen.queryByText('2')).not.toBeInTheDocument()
    // marked read first, then fetched again
    const log = fake.log()
    expect(log.lastIndexOf('GET /notifications')).toBeGreaterThan(log.indexOf('POST /notifications/read'))
  })

  it('marks read only once per visit', async () => {
    const fake = notifications([request()])
    renderApp(<NotificationsPage />, { api: fake.api })
    await screen.findByText('Dana ביקש/ה לעקוב אחריך')
    await vi.waitFor(() => expect(fake.count('POST /notifications/read')).toBe(1))
    expect(fake.count('POST /notifications/read')).toBe(1)
  })

  it('the sentence links to the profile of whoever it names', async () => {
    const fake = notifications([request()])
    renderApp(<NotificationsPage />, { api: fake.api })
    expect(await screen.findByRole('link', { name: 'Dana ביקש/ה לעקוב אחריך' })).toHaveAttribute(
      'href',
      '/u/dana',
    )
  })

  it('pending follow request shows Accept and Decline', async () => {
    const fake = notifications([request()])
    renderApp(<NotificationsPage />, { api: fake.api })
    expect(await screen.findByText('Dana ביקש/ה לעקוב אחריך')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: `${he.connections.accept} Dana` })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: `${he.connections.decline} Dana` })).toBeInTheDocument()
  })

  it('request_pending false shows plain text only', async () => {
    const fake = notifications([request({ request_pending: false })])
    renderApp(<NotificationsPage />, { api: fake.api })
    expect(await screen.findByText('Dana ביקש/ה לעקוב אחריך')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows accepted requests as text', async () => {
    const fake = notifications([request({ type: 'follow_accepted', request_pending: false })])
    renderApp(<NotificationsPage />, { api: fake.api })
    expect(await screen.findByText('Dana אישר/ה את בקשת המעקב שלך')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('accepts a request inline', async () => {
    const fake = notifications([request()])
    renderApp(<NotificationsPage />, { api: fake.api })
    await userEvent.click(await screen.findByRole('button', { name: `${he.connections.accept} Dana` }))
    await vi.waitFor(() => expect(screen.queryByRole('button')).not.toBeInTheDocument())
    expect(fake.count('POST /follow-requests/dana/accept')).toBe(1)
    expect(screen.getByText('Dana ביקש/ה לעקוב אחריך')).toBeInTheDocument()
  })

  it('declines a request inline', async () => {
    const fake = notifications([request()])
    renderApp(<NotificationsPage />, { api: fake.api })
    await userEvent.click(await screen.findByRole('button', { name: `${he.connections.decline} Dana` }))
    await vi.waitFor(() => expect(screen.queryByRole('button')).not.toBeInTheDocument())
    expect(fake.count('DELETE /follow-requests/dana')).toBe(1)
  })

  it('loads more notifications', async () => {
    const fake = fakeApi({
      'GET /notifications': { items: [request()], unread_count: 2, next_cursor: 'c1' },
      'GET /notifications?cursor=c1': {
        items: [request({ id: 2, type: 'follow_accepted', request_pending: false, actor: ERAN })],
        unread_count: 2,
        next_cursor: null,
      },
      'POST /notifications/read': () => undefined,
    })
    renderApp(<NotificationsPage />, { api: fake.api })
    await userEvent.click(await screen.findByRole('button', { name: he.common.loadMore }))
    expect(await screen.findByText('Eran אישר/ה את בקשת המעקב שלך')).toBeInTheDocument()
    expect(screen.getByText('Dana ביקש/ה לעקוב אחריך')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: he.common.loadMore })).not.toBeInTheDocument()
    expect(fake.count('GET /notifications?cursor=c1')).toBe(1)
  })

  it('has no Load more on the last page', async () => {
    const fake = notifications([request()])
    renderApp(<NotificationsPage />, { api: fake.api })
    await screen.findByText('Dana ביקש/ה לעקוב אחריך')
    expect(screen.queryByRole('button', { name: he.common.loadMore })).not.toBeInTheDocument()
  })

  it('shows an empty state', async () => {
    const fake = notifications([])
    renderApp(<NotificationsPage />, { api: fake.api })
    expect(await screen.findByText(he.notifications.empty)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: he.notifications.title })).toBeInTheDocument()
  })

  it('shows an error when notifications cannot be loaded', async () => {
    renderApp(<NotificationsPage />, { api: fakeApi({}).api })
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
  })
})
