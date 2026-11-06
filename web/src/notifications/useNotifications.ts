import { useMutation, useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query'
import type { NotificationItem } from '../api/types'
import { useApi } from '../api/useApi'

export const NOTIFICATIONS_KEY = ['notifications'] as const
export const NOTIFICATIONS_POLL_MS = 60_000

export type NotificationsResponse = { items: NotificationItem[]; unread_count: number }

/** The signed-in user's notifications; polled once a minute and refreshed when the window refocuses. */
export function useNotifications(): UseQueryResult<NotificationsResponse> {
  const api = useApi()
  return useQuery({
    queryKey: NOTIFICATIONS_KEY,
    refetchInterval: NOTIFICATIONS_POLL_MS,
    refetchOnWindowFocus: true,
    queryFn: ({ signal }) => api<NotificationsResponse>('/notifications', { signal }),
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
