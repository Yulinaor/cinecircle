import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { UserCard } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { DANA, fakeApi } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { ConnectionsPage } from './ConnectionsPage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const NOA: UserCard = { username: 'noa', display_name: 'נועה', avatar_url: null, follow_state: 'following' }
const RON: UserCard = { username: 'ron', display_name: 'Ron', avatar_url: null, follow_state: 'requested' }

/** Mutable in-memory lists so refetches after an action show the new state. */
function lists() {
  const state = {
    requests: [DANA] as UserCard[],
    followers: [DANA] as UserCard[],
    following: [NOA, RON],
  }
  return fakeApi({
    'GET /me/follow-requests': () => ({ users: state.requests }),
    'GET /me/followers': () => ({ users: state.followers }),
    'GET /me/following': () => ({ users: state.following }),
    'POST /follow-requests/dana/accept': () => {
      state.requests = []
      return DANA
    },
    'DELETE /follow-requests/dana': () => {
      state.requests = []
    },
    'DELETE /followers/dana': () => {
      state.followers = []
    },
  })
}

describe('ConnectionsPage', () => {
  it('opens on the requests tab', async () => {
    renderApp(<ConnectionsPage />, { api: lists().api })
    expect(screen.getByRole('heading', { name: he.connections.title })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: he.connections.requests })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(await screen.findByText('Dana')).toBeInTheDocument()
    expect(screen.getByText('@dana')).toBeInTheDocument()
  })

  it('accepts requests on the Connections page', async () => {
    const fake = lists()
    renderApp(<ConnectionsPage />, { api: fake.api })
    await userEvent.click(await screen.findByRole('button', { name: he.connections.accept }))
    expect(await screen.findByText(he.connections.empty)).toBeInTheDocument()
    expect(fake.count('POST /follow-requests/dana/accept')).toBe(1)
  })

  it('declines requests on the Connections page', async () => {
    const fake = lists()
    renderApp(<ConnectionsPage />, { api: fake.api })
    await userEvent.click(await screen.findByRole('button', { name: he.connections.decline }))
    expect(await screen.findByText(he.connections.empty)).toBeInTheDocument()
    expect(fake.count('DELETE /follow-requests/dana')).toBe(1)
  })

  it('removes a follower', async () => {
    const fake = lists()
    renderApp(<ConnectionsPage />, { api: fake.api })
    await userEvent.click(screen.getByRole('tab', { name: he.connections.followers }))
    await userEvent.click(await screen.findByRole('button', { name: he.connections.remove }))
    expect(await screen.findByText(he.connections.empty)).toBeInTheDocument()
    expect(fake.count('DELETE /followers/dana')).toBe(1)
  })

  it('lists who you follow with a follow control', async () => {
    renderApp(<ConnectionsPage />, { api: lists().api })
    await userEvent.click(screen.getByRole('tab', { name: he.connections.following }))
    const panel = await screen.findByRole('tabpanel')
    expect(await within(panel).findByText('נועה')).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: he.follow.following })).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: he.follow.requested })).toBeInTheDocument()
  })

  it('shows an error when a list cannot be loaded', async () => {
    renderApp(<ConnectionsPage />, { api: fakeApi({}).api })
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
  })
})
