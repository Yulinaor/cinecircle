import { act, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Me } from '../api/types'
import { useUserScopedCache } from '../api/useUserScopedCache'
import { FAKE_SESSION, renderApp } from '../test/renderApp'
import { ME_KEY, useUpdateMe } from './useMe'
import type { Session } from '@supabase/supabase-js'

const sessionOf = (id: string) => ({ ...FAKE_SESSION, user: { id } }) as Session
const meOf = (id: string, display_name: string): Me => ({
  id,
  email: null,
  profile: { username: id, display_name, avatar_url: null, bio: null, locale: 'en' },
})

// Stands in for AppShell: empties the cache whenever the signed-in user changes.
function Harness({ userId }: { userId: string }) {
  useUserScopedCache(userId)
  const update = useUpdateMe()
  return <button onClick={() => update.mutate({ display_name: 'New' })}>save</button>
}

describe('useUpdateMe', () => {
  it('writes the answer into the cache for the same user', async () => {
    const mine = meOf('a', 'A new')
    const { client } = renderApp(<Harness userId="a" />, {
      auth: { session: sessionOf('a') },
      api: (async () => mine) as never,
    })
    await act(async () => screen.getByRole('button', { name: 'save' }).click())
    expect(client.getQueryData(ME_KEY)).toEqual(mine)
  })

  it('does not put a late answer for user A into the cache of user B', async () => {
    let resolve!: (me: Me) => void
    const late = new Promise<Me>((r) => (resolve = r))
    const { client, rerender } = renderApp(<Harness userId="a" />, {
      auth: { session: sessionOf('a') },
      api: (() => late) as never,
    })
    await act(async () => screen.getByRole('button', { name: 'save' }).click())
    // The user switches to B (another tab) while A's PATCH is still in flight.
    await act(async () => rerender(<Harness userId="b" />, { session: sessionOf('b') }))
    client.setQueryData(ME_KEY, meOf('b', 'B original'))
    await act(async () => resolve(meOf('a', 'A new')))
    expect(client.getQueryData<Me>(ME_KEY)).toEqual(meOf('b', 'B original'))
  })
})
