import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { PostCard } from '../api/types'
import { useApi } from '../api/useApi'

export type NewPost = {
  title_id: number
  /** 0 = the whole movie / series. */
  season_number: number
  rating: number
  opinion: string | null
  contains_spoilers: boolean
  is_shared: boolean
}

/** Only what changed; `opinion: null` clears it. */
export type PostChanges = Partial<{
  rating: number
  opinion: string | null
  contains_spoilers: boolean
  is_shared: boolean
}>

/**
 * Create, edit and delete a post. Each one invalidates every post list, every title page and
 * every profile, since a post shows on all of them.
 */
export function usePostMutations() {
  const api = useApi()
  const client = useQueryClient()
  const invalidate = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: ['posts'] }),
      client.invalidateQueries({ queryKey: ['title'] }),
      client.invalidateQueries({ queryKey: ['profile'] }),
      // The wishlist shows your post's rating ("Your rating"), and a new post marks a wanted
      // title watched, server-side.
      client.invalidateQueries({ queryKey: ['wishlist'] }),
    ])

  const create = useMutation({
    mutationFn: (post: NewPost) => api<PostCard>('/posts', { method: 'POST', body: post }),
    onSuccess: invalidate,
  })
  const update = useMutation({
    mutationFn: ({ id, changes }: { id: number; changes: PostChanges }) =>
      api<PostCard>(`/posts/${id}`, { method: 'PATCH', body: changes }),
    // Awaited: the post page we go to next then already has the fresh card.
    onSuccess: invalidate,
  })
  const remove = useMutation({
    mutationFn: (id: number) => api<void>(`/posts/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      // Not awaited: the page the caller leaves must not refetch the deleted post and flash
      // "Not found" before the navigation lands.
      void invalidate()
    },
  })
  return { create, update, remove }
}
