import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import type { PostCard } from '../api/types'
import { useApi } from '../api/useApi'
import { useLang } from '../i18n/useLang'
import { postKeys } from './keys'

/** The id from a `/posts/:id` URL, or null when it isn't a positive integer the API could hold. */
export function parsePostId(raw: string | undefined): number | null {
  if (raw === undefined || !/^[1-9]\d*$/.test(raw)) return null
  const id = Number(raw)
  return Number.isSafeInteger(id) ? id : null
}

/** One post as the card shows it, in the UI language. A missing or hidden post is a 404 ApiError. */
export function usePost(id: number): UseQueryResult<PostCard> {
  const api = useApi()
  const lang = useLang()
  return useQuery({
    queryKey: postKeys.one(id, lang),
    queryFn: ({ signal }) => api<PostCard>(`/posts/${id}?lang=${lang}`, { signal }),
  })
}
