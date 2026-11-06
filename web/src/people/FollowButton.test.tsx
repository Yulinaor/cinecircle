import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { FollowState } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { fakeApi } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { FollowButton } from './FollowButton'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

describe('FollowButton', () => {
  it.each([
    ['none', he.follow.follow, en.follow.follow],
    ['requested', he.follow.requested, en.follow.requested],
    ['following', he.follow.following, en.follow.following],
  ] as [FollowState, string, string][])(
    'FollowButton shows %s in Hebrew and English',
    async (state, hebrew, english) => {
      renderApp(<FollowButton username="gal" state={state} />, { api: fakeApi({}).api })
      expect(screen.getByRole('button', { name: hebrew })).toBeInTheDocument()
      await setLocale('en')
      expect(await screen.findByRole('button', { name: english })).toBeInTheDocument()
    },
  )

  it('has the exact Hebrew labels', () => {
    expect([he.follow.follow, he.follow.requested, he.follow.following]).toEqual([
      'מעקב',
      'נשלחה בקשה',
      'במעקב',
    ])
  })

  it('renders nothing for yourself', () => {
    const { container } = renderApp(<FollowButton username="me" state="self" />, {
      api: fakeApi({}).api,
    })
    expect(container).toBeEmptyDOMElement()
  })

  it('Follow sends a request and shows Requested', async () => {
    const fake = fakeApi({ 'POST /follows/gal': { follow_state: 'requested' } })
    renderApp(<FollowButton username="gal" state="none" />, { api: fake.api })
    await userEvent.click(screen.getByRole('button', { name: he.follow.follow }))
    expect(await screen.findByRole('button', { name: he.follow.requested })).toBeEnabled()
    expect(fake.log()).toEqual(['POST /follows/gal'])
  })

  it('shows Following when the answer is an immediate follow', async () => {
    const fake = fakeApi({ 'POST /follows/gal': { follow_state: 'following' } })
    renderApp(<FollowButton username="gal" state="none" />, { api: fake.api })
    await userEvent.click(screen.getByRole('button', { name: he.follow.follow }))
    expect(await screen.findByRole('button', { name: he.follow.following })).toBeEnabled()
  })

  it('Requested cancels the request', async () => {
    const fake = fakeApi({ 'DELETE /follows/gal': () => undefined })
    renderApp(<FollowButton username="gal" state="requested" />, { api: fake.api })
    await userEvent.click(screen.getByRole('button', { name: he.follow.requested }))
    expect(await screen.findByRole('button', { name: he.follow.follow })).toBeEnabled()
    expect(fake.log()).toEqual(['DELETE /follows/gal'])
  })

  it('Following unfollows', async () => {
    const fake = fakeApi({ 'DELETE /follows/gal': () => undefined })
    renderApp(<FollowButton username="gal" state="following" />, { api: fake.api })
    await userEvent.click(screen.getByRole('button', { name: he.follow.following }))
    expect(await screen.findByRole('button', { name: he.follow.follow })).toBeEnabled()
    expect(fake.log()).toEqual(['DELETE /follows/gal'])
  })

  it('is disabled while sending and reverts the label when the request fails', async () => {
    let fail: (error: ApiError) => void = () => {}
    const fake = fakeApi({
      'POST /follows/gal': () => new Promise((_, reject) => (fail = reject)),
    })
    renderApp(<FollowButton username="gal" state="none" />, { api: fake.api })
    await userEvent.click(screen.getByRole('button', { name: he.follow.follow }))
    expect(await screen.findByRole('button', { name: he.follow.requested })).toBeDisabled()
    fail(new ApiError(500, 'error'))
    expect(await screen.findByRole('button', { name: he.follow.follow })).toBeEnabled()
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
  })

  it('follows the server state again after it changes and changes back', async () => {
    const fake = fakeApi({ 'POST /follows/gal': { follow_state: 'requested' } })
    const view = renderApp(<FollowButton username="gal" state="none" />, { api: fake.api })
    await userEvent.click(screen.getByRole('button', { name: he.follow.follow }))
    expect(await screen.findByRole('button', { name: he.follow.requested })).toBeEnabled()
    // the refetch says requested; later they declined and the server says none again
    view.rerender(<FollowButton username="gal" state="requested" />)
    expect(screen.getByRole('button', { name: he.follow.requested })).toBeInTheDocument()
    view.rerender(<FollowButton username="gal" state="none" />)
    expect(screen.getByRole('button', { name: he.follow.follow })).toBeInTheDocument()
  })

  it('is named after the person when it sits in a list', () => {
    renderApp(
      <>
        <span id="who">Gal</span>
        <FollowButton username="gal" state="none" nameId="who" />
      </>,
      { api: fakeApi({}).api },
    )
    expect(screen.getByRole('button', { name: `${he.follow.follow} Gal` })).toBeInTheDocument()
  })

  it('refetches people and connections after a change', async () => {
    const fake = fakeApi({ 'POST /follows/gal': { follow_state: 'requested' } })
    const { client } = renderApp(<FollowButton username="gal" state="none" />, { api: fake.api })
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    await userEvent.click(screen.getByRole('button', { name: he.follow.follow }))
    await screen.findByRole('button', { name: he.follow.requested })
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey)
    expect(keys).toEqual(expect.arrayContaining([['people'], ['connections']]))
  })
})
