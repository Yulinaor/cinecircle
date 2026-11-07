import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { WishlistItem, WishlistSource, WishlistStatus } from '../api/types'
import { useApi } from '../api/useApi'
import { postKeys } from '../posts/keys'
import { wishlistKeys } from './keys'

export type NewWishlistItem = {
  title_id: number
  source: WishlistSource
  /** Required with source `post`, forbidden with any other. */
  source_post_id?: number
}

/**
 * Save, move and remove wishlist items. Each one invalidates the wishlist and every post list
 * and title page (their cards show whether the title is saved). Not awaited, so the caller is
 * usable again without waiting for those refetches.
 */
export function useWishlistMutations() {
  const api = useApi()
  const client = useQueryClient()
  const invalidate = () => {
    void client.invalidateQueries({ queryKey: wishlistKeys.all })
    void client.invalidateQueries({ queryKey: postKeys.all })
    void client.invalidateQueries({ queryKey: ['title'] })
  }

  const save = useMutation({
    mutationFn: (item: NewWishlistItem) =>
      api<WishlistItem>('/wishlist', { method: 'POST', body: item }),
    onSuccess: invalidate,
  })
  const setStatus = useMutation({
    mutationFn: ({ titleId, status }: { titleId: number; status: WishlistStatus }) =>
      api<WishlistItem>(`/wishlist/${titleId}`, { method: 'PATCH', body: { status } }),
    onSuccess: invalidate,
  })
  const remove = useMutation({
    mutationFn: (titleId: number) => api<void>(`/wishlist/${titleId}`, { method: 'DELETE' }),
    onSuccess: invalidate,
  })
  return { save, setStatus, remove }
}
