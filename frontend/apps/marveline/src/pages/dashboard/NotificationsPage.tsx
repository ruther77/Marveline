import { useState } from 'react'
import { Bell, Check, CheckCheck } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { PageHeader } from '@shared/components/ui/Breadcrumb'
import { useNotifications, useMarkNotificationRead, useMarkAllNotificationsRead } from '@/api/queries/useNotifications'
import { ActionError } from '@shared/components/ui/ActionError'
import { formatDistanceToNow } from 'date-fns'
import { fr } from 'date-fns/locale'
import { Link } from '@tanstack/react-router'

export default function NotificationsPage() {
  const [error, setError] = useState<string | null>(null)
  const { data, isLoading, error: queryError, refetch } = useNotifications()
  const markRead = useMarkNotificationRead()
  const markAllRead = useMarkAllNotificationsRead()

  const errHandler = (err: unknown) => setError(
    normalizeError(err).message || 'Une erreur est survenue'
  )

  const notifications = data?.items ?? []
  const unreadCount = data?.unread_count ?? 0

  return (
    <div className="space-y-6">
      <ActionError message={error} onDismiss={() => setError(null)} />

      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="Notifications"
          subtitle={unreadCount > 0 ? `${unreadCount} non lue${unreadCount > 1 ? 's' : ''}` : 'Tout est à jour'}
        />
        {unreadCount > 0 && (
          <button
            onClick={() => markAllRead.mutate(undefined, { onError: errHandler })}
            disabled={markAllRead.isPending}
            className="shrink-0 flex items-center gap-1.5 text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            <CheckCheck className="w-4 h-4" />
            Tout marquer comme lu
          </button>
        )}
      </div>

      {queryError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="card p-0 divide-y divide-dark-600 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-start gap-4 px-6 py-4">
              <div className="mt-0.5 w-2 h-2 rounded-full skel shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-1/3" />
                <div className="h-2 skel rounded w-2/3" />
              </div>
            </div>
          ))}
        </div>
      ) : notifications.length === 0 ? (
        <div className="card p-12 text-center">
          <Bell className="w-10 h-10 text-dark-600 mx-auto mb-4" />
          <p className="text-sm text-dark-400">Aucune notification</p>
        </div>
      ) : (
        <div className="card p-0 divide-y divide-dark-600">
          {notifications.map((n) => (
            <div
              key={n.id}
              className={`flex items-start gap-4 px-6 py-4 ${!n.is_read ? 'bg-primary-500/10' : ''}`}
            >
              <div className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${!n.is_read ? 'bg-primary-500' : 'bg-transparent'}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className={`text-sm font-medium ${!n.is_read ? 'text-white' : 'text-dark-300'}`}>
                    {n.link ? (
                      <Link to={n.link as never} className="hover:underline">{n.title}</Link>
                    ) : n.title}
                  </p>
                  <span className="text-xs text-dark-500">
                    {formatDistanceToNow(new Date(n.created_at), { addSuffix: true, locale: fr })}
                  </span>
                </div>
                {n.message && (
                  <p className="text-xs text-dark-400 mt-0.5">{n.message}</p>
                )}
              </div>
              {!n.is_read && (
                <button
                  onClick={() => markRead.mutate(n.id, { onError: errHandler })}
                  disabled={markRead.isPending}
                  title="Marquer comme lu"
                  className="shrink-0 text-dark-500 hover:text-primary-600"
                >
                  <Check className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
