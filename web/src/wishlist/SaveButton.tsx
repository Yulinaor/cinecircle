import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { WishlistSource } from '../api/types'
import { useWishlistMutations } from './useWishlistMutations'

/**
 * Save to wishlist / Saved, one toggle. The label changes only when the server has answered (the
 * button is disabled until then), so a failed save, including a 404 for a post that was
 * unshared meanwhile, never looks saved. Pressing Saved removes the title from the list.
 */
export function SaveButton({
  titleId,
  saved,
  source,
  sourcePostId,
}: {
  titleId: number
  saved: boolean
  source: WishlistSource
  /** The post being saved from; only with source `post`. */
  sourcePostId?: number
}) {
  const { t } = useTranslation()
  const { save, remove } = useWishlistMutations()
  // What the button shows until the parent hands us a new server state; then the server wins.
  const [local, setLocal] = useState<boolean | null>(null)
  const [seenSaved, setSeenSaved] = useState(saved)
  if (seenSaved !== saved) {
    // Adjusted during render (not in an effect), so a stale value never paints.
    setSeenSaved(saved)
    setLocal(null)
  }
  const shown = local ?? saved
  const pending = save.isPending || remove.isPending
  const failed = save.isError || remove.isError

  const press = () => {
    save.reset()
    remove.reset()
    if (shown) {
      remove.mutate(titleId, { onSuccess: () => setLocal(false) })
    } else {
      save.mutate(
        {
          title_id: titleId,
          source,
          ...(sourcePostId !== undefined && { source_post_id: sourcePostId }),
        },
        { onSuccess: () => setLocal(true) },
      )
    }
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <button
        type="button"
        aria-pressed={shown}
        disabled={pending}
        onClick={press}
        className={`min-h-11 rounded-xl px-4 text-sm font-semibold disabled:opacity-60 ${
          shown
            ? 'bg-accent-soft text-accent hover:opacity-90'
            : 'border border-line bg-surface text-ink hover:bg-bg'
        }`}
      >
        {t(shown ? 'wishlist.saved' : 'wishlist.save')}
      </button>
      {failed && (
        <p role="alert" className="text-xs font-medium text-danger">
          {t('common.error')}
        </p>
      )}
    </div>
  )
}
