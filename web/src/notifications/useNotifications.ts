import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
  type UseInfiniteQueryResult,
} from '@tanstack/react-query'
import type { NotificationItem } from '../api/types'
import { useApi } from '../api/useApi'

export const NOTIFICATIONS_KEY = ['notifications'] as const
export const NOTIFICATIONS_POLL_MS = 60_000

/** One page of `GET /notifications`; `unread_count` always counts every unread notification. */
export type NotificationsResponse = {
  items: NotificationItem[]
  unread_count: number
  next_cursor: string | null
}

/** All loaded pages as one list: `unread_count` is the first (freshest) page's, `next_cursor` the last's. */
function joinPages(data: InfiniteData<NotificationsResponse, string | null>): NotificationsResponse {
  const first = data.pages[0]
  const last = data.pages[data.pages.length - 1]
  return {
    items: data.pages.flatMap((page) => page.items),
    unread_count: first.unread_count,
    next_cursor: last.next_cursor,
  }
}

/**
 * The signed-in user's notifications, newest first, a page at a time (`fetchNextPage` appends the
 * next one). Polled once a minute and refreshed when the window refocuses; a refetch reloads every
 * loaded page in order, so appended pages stay and pick up changes (e.g. an accepted request).
 */
export function useNotifications(): UseInfiniteQueryResult<NotificationsResponse> {
  const api = useApi()
  return useInfiniteQuery({
    queryKey: NOTIFICATIONS_KEY,
    refetchInterval: NOTIFICATIONS_POLL_MS,
    refetchOnWindowFocus: true,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<NotificationsResponse>(
        pageParam === null ? '/notifications' : `/notifications?cursor=${encodeURIComponent(pageParam)}`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor,
    select: joinPages,
  })
}

/** `POST /notifications/read`, then a refetch so the badge and the rows catch up. */
export function useMarkNotificationsRead() {
  const api = useApi()
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<void>('/notifications/read', { method: 'POST' }),
    onSuccess: () => client.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
  })
}
