import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import type { UserProfile } from '../api/types'
import { useApi } from '../api/useApi'

export const profileKey = (username: string) => ['profile', username] as const

/**
 * `GET /users/{username}`: the card for anyone, plus `details` (bio, counts) once the viewer may
 * see them. An unknown user is a 404 ApiError. Post mutations and follow actions invalidate
 * `['profile']`, so this follows the viewer's relationship and the shown counts.
 */
export function useProfile(username: string): UseQueryResult<UserProfile> {
  const api = useApi()
  return useQuery({
    queryKey: profileKey(username),
    queryFn: ({ signal }) => api<UserProfile>(`/users/${encodeURIComponent(username)}`, { signal }),
  })
}
