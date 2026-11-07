import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../api/client'
import type { TitleDetail, TitleSearchItem, WishlistStatus } from '../api/types'
import { useApi } from '../api/useApi'
import { TitlePicker } from '../compose/TitlePicker'
import { useLang } from '../i18n/useLang'
import { useWishlistMutations } from './useWishlistMutations'

const SECONDARY =
  'min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line'

/**
 * Search for a movie or series and save it as Want (source `search`). The picked result is cached
 * through `/titles/tmdb/...` first, which also gives its id; `onDone` runs once it is saved, and
 * on Cancel.
 */
export function AddToWishlist({
  onDone,
  onAdded,
}: {
  onDone: () => void
  /** Only after a save, before `onDone`, with the saved item's status (it may have been there already). */
  onAdded?: (status: WishlistStatus) => void
}) {
  const { t } = useTranslation()
  const api = useApi()
  const lang = useLang()
  const { save } = useWishlistMutations()
  const detail = useMutation({
    mutationFn: (item: TitleSearchItem) =>
      api<TitleDetail>(`/titles/tmdb/${item.media_type}/${item.tmdb_id}?lang=${lang}`),
  })

  // Two requests, one after the other; each one's own state says which one failed.
  const add = (item: TitleSearchItem) => {
    save.reset()
    detail.mutate(item, {
      onSuccess: (found) =>
        save.mutate(
          { title_id: found.id, source: 'search' },
          {
            onSuccess: (item) => {
              onAdded?.(item.status)
              onDone()
            },
          },
        ),
    })
  }

  const busy = detail.isPending || save.isPending
  const error = detail.error ?? save.error

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-3">
      {busy ? (
        <p role="status" className="text-muted">
          {t('auth.loading')}
        </p>
      ) : error && detail.variables ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="text-sm font-medium text-danger">
            {error instanceof ApiError && error.detail === 'catalog_unavailable'
              ? t('compose.errors.catalog_unavailable')
              : t('common.error')}
          </p>
          <button type="button" onClick={() => add(detail.variables)} className={SECONDARY}>
            {t('common.retry')}
          </button>
        </div>
      ) : (
        <TitlePicker onPick={add} />
      )}
      <button type="button" onClick={onDone} className={`${SECONDARY} self-start`}>
        {t('wishlist.cancel')}
      </button>
    </div>
  )
}
