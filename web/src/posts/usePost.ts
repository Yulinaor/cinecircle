import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import type { PostCard } from '../api/types'
import { useApi } from '../api/useApi'
import { useLang } from '../i18n/useLang'
import { postKeys } from './keys'

/** One post as the card shows it, in the UI language. A missing or hidden post is a 404 ApiError. */
export function usePost(id: number): UseQueryResult<PostCard> {
  const api = useApi()
  const lang = useLang()
  return useQuery({
    queryKey: postKeys.one(id, lang),
    queryFn: ({ signal }) => api<PostCard>(`/posts/${id}?lang=${lang}`, { signal }),
  })
}
