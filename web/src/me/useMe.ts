import { useMutation, useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import type { Me } from '../api/types'
import { useApi } from '../api/useApi'
import { useAuth } from '../auth/AuthProvider'
import { currentLocale, setLocale } from '../i18n'

export const ME_KEY = ['me'] as const

export type ProfileChanges = { display_name?: string; bio?: string; locale?: 'he' | 'en' }

/**
 * The signed-in user's account, fetched once per sign-in (updates arrive through `useUpdateMe` or
 * an explicit invalidation). When the account's language differs from the UI's, the account wins
 * — on each load only, so a later in-app switch (which is saved to the account) is never undone.
 */
export function useMe(): UseQueryResult<Me> {
  const api = useApi()
  return useQuery({
    queryKey: ME_KEY,
    staleTime: Infinity,
    queryFn: async ({ signal }) => {
      const me = await api<Me>('/me', { signal })
      // The user may have changed (cancelled via the cache reset) while this was in flight.
      if (signal.aborted) return me
      if (me.profile && me.profile.locale !== currentLocale()) await setLocale(me.profile.locale)
      return me
    },
  })
}

/**
 * `PATCH /me`; keeps the cached account in step with the answer — unless the signed-in user
 * changed while it was in flight: the cache then belongs to someone else and must not receive
 * this user's profile.
 */
export function useUpdateMe() {
  const api = useApi()
  const client = useQueryClient()
  const userId = useAuth().session?.user.id ?? null
  const current = useRef(userId)
  useEffect(() => {
    current.current = userId
  }, [userId])
  return useMutation({
    mutationFn: (changes: ProfileChanges) => api<Me>('/me', { method: 'PATCH', body: changes }),
    onMutate: () => ({ userId: current.current }),
    onSuccess: (me, _changes, context) => {
      if (context?.userId === current.current) client.setQueryData(ME_KEY, me)
    },
  })
}
