import { useInfiniteQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { WishlistPage as WishlistPageData, WishlistStatus } from '../api/types'
import { useApi } from '../api/useApi'
import { useLang } from '../i18n/useLang'
import { AddToWishlist } from './AddToWishlist'
import { wishlistKeys } from './keys'
import { WishlistRow } from './WishlistRow'

const STATUSES = ['want', 'watched'] as const satisfies readonly WishlistStatus[]

const BUTTON =
  'min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line disabled:opacity-60'

/** `/wishlist`: your private list, Want to watch and Watched, newest first. */
export function WishlistPage() {
  const { t } = useTranslation()
  const api = useApi()
  const lang = useLang()
  const [status, setStatus] = useState<WishlistStatus>('want')
  const [adding, setAdding] = useState(false)

  const list = useInfiniteQuery({
    queryKey: wishlistKeys.list(status, lang),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<WishlistPageData>(
        `/wishlist?status=${status}&lang=${lang}${pageParam === null ? '' : `&cursor=${encodeURIComponent(pageParam)}`}`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor,
  })
  const { data, isError, isFetching, hasNextPage, fetchNextPage, refetch } = list
  // Retry repeats whichever fetch failed: the next page, or a refetch of what is loaded.
  const loadMoreFailed = useRef(false)

  const loadMore = () => {
    loadMoreFailed.current = true
    void fetchNextPage().then((result) => {
      loadMoreFailed.current = result.isError
    })
  }
  const retry = () => {
    if (loadMoreFailed.current && hasNextPage) loadMore()
    else void refetch()
  }

  const items = data?.pages.flatMap((p) => p.items) ?? []
  const errorLine = isError && (
    <div role="alert" className="flex flex-col items-start gap-3">
      <p className="text-sm font-medium text-danger">{t('common.error')}</p>
      <button type="button" onClick={retry} disabled={isFetching} className={BUTTON}>
        {t('common.retry')}
      </button>
    </div>
  )

  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      <h1 className="text-2xl font-extrabold">{t('nav.wishlist')}</h1>
      <p className="text-sm text-muted">{t('wishlist.privateNote')}</p>
      <div className="flex flex-wrap gap-2">
        {STATUSES.map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={status === value}
            onClick={() => setStatus(value)}
            className={`min-h-11 rounded-full border px-4 font-medium ${
              status === value
                ? 'border-accent bg-accent-soft text-accent'
                : 'border-line bg-surface text-ink hover:bg-line'
            }`}
          >
            {t(`wishlist.tab.${value}`)}
          </button>
        ))}
      </div>
      {adding ? (
        <AddToWishlist onDone={() => setAdding(false)} onAdded={() => setStatus('want')} />
      ) : (
        <button type="button" onClick={() => setAdding(true)} className={`${BUTTON} self-start`}>
          {t('wishlist.add')}
        </button>
      )}

      {!data ? (
        errorLine || (
          <p role="status" className="text-muted">
            {t('auth.loading')}
          </p>
        )
      ) : items.length === 0 && !isError ? (
        <p className="text-muted">{t(`wishlist.empty.${status}`)}</p>
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {items.map((item) => (
              <WishlistRow key={item.title.id} item={item} />
            ))}
          </ul>
          {errorLine}
          {!isError && hasNextPage && (
            <button type="button" onClick={loadMore} disabled={isFetching} className={BUTTON}>
              {t('common.loadMore')}
            </button>
          )}
        </>
      )}
    </section>
  )
}
