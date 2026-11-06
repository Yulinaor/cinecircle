import type { Session } from '@supabase/supabase-js'
import { act, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Me } from '../api/types'
import { useUserScopedCache } from '../api/useUserScopedCache'
import { FAKE_SESSION, renderApp } from '../test/renderApp'
import { ME_KEY, useUpdateMe } from './useMe'

const sessionOf = (id: string) => ({ ...FAKE_SESSION, user: { id } }) as Session
const meOf = (id: string, display_name: string): Me => ({
  id,
  email: null,
  profile: { username: id, display_name, avatar_url: null, bio: null, locale: 'en' },
})

function SaveButton() {
  const update = useUpdateMe()
  return <button onClick={() => update.mutate({ display_name: 'New' })}>save</button>
}

// Stands in for AppShell: empties the cache whenever the signed-in user changes, and (like
// AppShell while the cache is not ready) renders nothing in place of the page, so the page that
// started the PATCH is unmounted on an A -> B switch.
function Harness({ userId }: { userId: string }) {
  const ready = useUserScopedCache(userId)
  return ready ? <SaveButton /> : <p>loading</p>
}

const save = () => act(async () => screen.getByRole('button', { name: 'save' }).click())

describe('useUpdateMe', () => {
  it('updates the cached account at once for the same user', async () => {
    const mine = meOf('a', 'A new')
    const { client } = renderApp(<Harness userId="a" />, {
      auth: { session: sessionOf('a') },
      api: (async () => mine) as never,
    })
    await screen.findByRole('button', { name: 'save' })
    client.setQueryData(ME_KEY, meOf('a', 'A old'))
    await save()
    expect(client.getQueryData(ME_KEY)).toEqual(mine)
  })

  it('does not put a late answer for user A into the cache of user B', async () => {
    let resolve!: (me: Me) => void
    const late = new Promise<Me>((r) => (resolve = r))
    const { client, rerender } = renderApp(<Harness userId="a" />, {
      auth: { session: sessionOf('a') },
      api: (() => late) as never,
    })
    await screen.findByRole('button', { name: 'save' })
    client.setQueryData(ME_KEY, meOf('a', 'A old'))
    await save()
    // The user switches to B while A's PATCH is in flight: the page that sent it unmounts (and a new one mounts) ...
    await act(async () => rerender(<Harness userId="b" />, { session: sessionOf('b') }))
    // ... B's own /me arrives ...
    client.setQueryData(ME_KEY, meOf('b', 'B original'))
    // ... and then A's answer.
    await act(async () => resolve(meOf('a', 'A new')))
    expect(client.getQueryData<Me>(ME_KEY)).toEqual(meOf('b', 'B original'))
  })

  it('does not create the cache entry from a late answer either', async () => {
    let resolve!: (me: Me) => void
    const late = new Promise<Me>((r) => (resolve = r))
    const { client, rerender } = renderApp(<Harness userId="a" />, {
      auth: { session: sessionOf('a') },
      api: (() => late) as never,
    })
    await screen.findByRole('button', { name: 'save' })
    await save()
    await act(async () => rerender(<Harness userId="b" />, { session: sessionOf('b') }))
    await act(async () => resolve(meOf('a', 'A new')))
    expect(client.getQueryData(ME_KEY)).toBeUndefined()
  })
})
