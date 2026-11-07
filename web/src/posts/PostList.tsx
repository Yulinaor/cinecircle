import type { InfiniteData, UseInfiniteQueryResult } from '@tanstack/react-query'
import { useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { PostPage } from '../api/types'
import { PostCard } from './PostCard'

const BUTTON =
  'min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line disabled:opacity-60'

/**
 * The pages of a `useInfiniteQuery<PostPage>` as post cards, with Load more while there is a next
 * page. Once something has loaded it stays on screen: a failed refetch or Load more shows the error
 * line with a retry under the cards; only a query with no data at all shows the error alone.
 */
export function PostList({
  query,
  empty,
}: {
  query: UseInfiniteQueryResult<InfiniteData<PostPage>>
  /** Shown when the first page has no posts. */
  empty: ReactNode
}) {
  const { t } = useTranslation()
  const { data, isError, isFetching, hasNextPage, fetchNextPage, refetch } = query
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

  const errorLine = isError && (
    <div role="alert" className="flex flex-col items-start gap-3">
      <p className="text-sm font-medium text-danger">{t('common.error')}</p>
      <button type="button" onClick={retry} disabled={isFetching} className={BUTTON}>
        {t('common.retry')}
      </button>
    </div>
  )

  if (!data) {
    return (
      errorLine || (
        <p role="status" className="text-muted">
          {t('auth.loading')}
        </p>
      )
    )
  }

  const posts = data.pages.flatMap((p) => p.posts)
  if (posts.length === 0 && !isError) return <>{empty}</>

  return (
    <>
      <div className="flex flex-col gap-4">
        {posts.map((post) => (
          <PostCard key={post.id} post={post} />
        ))}
      </div>
      {errorLine}
      {!isError && hasNextPage && (
        <button type="button" onClick={loadMore} disabled={isFetching} className={BUTTON}>
          {t('common.loadMore')}
        </button>
      )}
    </>
  )
}
