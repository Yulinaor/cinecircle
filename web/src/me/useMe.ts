import { useMutation, useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query'
import type { Me } from '../api/types'
import { useApi } from '../api/useApi'
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
 * `PATCH /me`; keeps the cached account in step with the answer. The write is decided by the
 * cache itself, not by the caller (which may be gone): it replaces the cached account only if
 * that is the same user's, so a late answer never lands in the cache of whoever signed in since.
 */
export function useUpdateMe() {
  const api = useApi()
  const client = useQueryClient()
  return useMutation({
    mutationFn: (changes: ProfileChanges) => api<Me>('/me', { method: 'PATCH', body: changes }),
    onSuccess: (me) =>
      client.setQueryData<Me>(ME_KEY, (old) => (old && old.id === me.id ? me : old)),
  })
}
