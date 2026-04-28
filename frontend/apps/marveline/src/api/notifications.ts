import { api } from './fetchClient'
import type { Notification, NotificationList } from '../types/notification'

export const notificationsApi = {
  list: (params?: { unread_only?: boolean; skip?: number; limit?: number }): Promise<NotificationList> => {
    const p = new URLSearchParams()
    if (params?.unread_only) p.set('unread_only', 'true')
    if (params?.skip != null) p.set('skip', String(params.skip))
    if (params?.limit != null) p.set('limit', String(params.limit))
    const qs = p.toString()
    return api.get<NotificationList>(`/notifications${qs ? `?${qs}` : ''}`)
  },

  markRead: (id: number): Promise<Notification> =>
    api.post<Notification>(`/notifications/${id}/read`, {}),

  markAllRead: (): Promise<{ marked_read: number }> =>
    api.post<{ marked_read: number }>('/notifications/read-all', {}),
}
