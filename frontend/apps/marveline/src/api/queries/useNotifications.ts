import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AuthError, ForbiddenError } from '@shared/errors/types'
import { notificationsApi } from '../notifications'
import { useAuthStore } from '@/stores/authStore'

const KEYS = {
  all: ['notifications'] as const,
  list: (params?: { unread_only?: boolean }) => ['notifications', 'list', params] as const,
}

const NOTIFICATIONS_POLL_INTERVAL_MS = 30_000

export function canPollNotifications(isAuthenticated: boolean, hasUser: boolean) {
  return isAuthenticated && hasUser
}

export function shouldRetryNotifications(failureCount: number, error: unknown) {
  if (error instanceof AuthError || error instanceof ForbiddenError) {
    return false
  }
  return failureCount < 1
}

export function useNotifications(params?: { unread_only?: boolean }) {
  const canPoll = useAuthStore((state) => canPollNotifications(state.isAuthenticated, !!state.user))

  return useQuery({
    queryKey: KEYS.list(params),
    queryFn: () => notificationsApi.list(params),
    enabled: canPoll,
    refetchInterval: canPoll ? NOTIFICATIONS_POLL_INTERVAL_MS : false,
    refetchIntervalInBackground: false,
    retry: shouldRetryNotifications,
  })
}

export function useMarkNotificationRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => notificationsApi.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  })
}

export function useMarkAllNotificationsRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  })
}
