import { useRef } from 'react'

/** What of a `useInfiniteQuery` result the hook needs. */
type PagedQuery = {
  hasNextPage: boolean
  fetchNextPage: () => Promise<{ isError: boolean }>
  refetch: () => unknown
}

/**
 * Load more / Try again for a paged list. Retry repeats whichever fetch failed: the next page, or a
 * refetch of what is loaded. `scope` names the list being shown (its filter, language, ...): a
 * failed Load more on one list never makes Retry fetch the next page of another.
 */
export function useLoadMoreRetry(
  query: PagedQuery,
  scope = '',
) {
  const { hasNextPage, fetchNextPage, refetch } = query
  // The scope the last Load more failed in, or null.
  const failedIn = useRef<string | null>(null)

  const loadMore = () => {
    failedIn.current = scope
    void fetchNextPage().then((result) => {
      failedIn.current = result.isError ? scope : null
    })
  }
  const retry = () => {
    if (failedIn.current === scope && hasNextPage) loadMore()
    else void refetch()
  }
  return { loadMore, retry }
}
