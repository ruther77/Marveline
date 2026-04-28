import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { Bell, CheckCircle, XCircle, Clock, Mail, Smartphone, Filter } from 'lucide-react'
import { ActionError } from '@shared/components/ui/ActionError'
import { useRelances, useCancelRelance, useMarkRelanceSent } from '@/api/queries'
import { normalizeError } from '@shared/errors/normalizer'
import type { RelanceChannel } from '@/types/relance'
import { formatDate } from '@/lib/utils'
import { cn } from '@/lib/utils'

const CHANNEL_LABELS: Record<RelanceChannel, string> = {
  email: 'Email',
  sms: 'SMS',
  push: 'Push',
}

const CHANNEL_ICONS: Record<RelanceChannel, React.ReactNode> = {
  email: <Mail className="w-3.5 h-3.5" />,
  sms: <Smartphone className="w-3.5 h-3.5" />,
  push: <Bell className="w-3.5 h-3.5" />,
}

type StatusFilter = 'scheduled' | 'sent' | 'all'

export default function ClientsRelancesPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('scheduled')
  const [error, setError] = useState<string | null>(null)

  const { data: relancesData, isLoading } = useRelances()
  const relances = relancesData?.items ?? []

  const errHandler = (err: unknown) => setError(
    normalizeError(err).message || 'Une erreur est survenue'
  )

  const cancelMutation = useCancelRelance()
  const markSentMutation = useMarkRelanceSent()

  const filtered = relances.filter((r) => {
    if (statusFilter === 'all') return true
    return r.status === statusFilter
  })

  const scheduledCount = relances.filter((r) => r.status === 'scheduled').length
  const sentCount = relances.filter((r) => r.status === 'sent').length

  return (
    <div className="space-y-6">
      <ActionError message={error} onDismiss={() => setError(null)} />

      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Relances planifiées" subtitle={`${scheduledCount} en attente · ${sentCount} envoyées`} />
        <Link
          to="/customers"
          className="text-sm text-dark-400 hover:text-dark-50 flex items-center gap-1.5"
        >
          ← Clients
        </Link>
      </div>

      {/* Filtres statut */}
      <div className="flex gap-2">
        {([
          { value: 'scheduled', label: 'En attente', count: scheduledCount },
          { value: 'sent', label: 'Envoyées', count: sentCount },
          { value: 'all', label: 'Toutes', count: relances.length },
        ] as { value: StatusFilter; label: string; count: number }[]).map(({ value, label, count }) => (
          <button
            key={value}
            onClick={() => setStatusFilter(value)}
            className={cn(
              'flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-medium transition-colors',
              statusFilter === value
                ? 'bg-gold-500 text-dark-900'
                : 'btn-secondary'
            )}
          >
            <Filter className="w-3.5 h-3.5" />
            {label}
            <span className="bg-dark-600 text-dark-300 rounded-full px-1.5 py-0 text-xs">
              {count}
            </span>
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="card p-0 divide-y divide-dark-600 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between px-4 py-4">
              <div className="flex items-start gap-4 min-w-0 flex-1">
                <div className="w-8 h-8 rounded-full skel shrink-0" />
                <div className="space-y-2 flex-1">
                  <div className="h-3 skel rounded w-24" />
                  <div className="h-2 skel rounded w-40" />
                </div>
              </div>
              <div className="h-6 skel rounded w-16 shrink-0" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-12">
          <Bell className="w-10 h-10 text-dark-600 mx-auto mb-4" />
          <p className="text-dark-400">Aucune relance{statusFilter === 'scheduled' ? ' en attente' : ''}</p>
        </div>
      ) : (
        <div className="card p-0 divide-y divide-dark-600">
          {filtered.map((relance) => (
            <div key={relance.id} className="flex items-center justify-between px-4 py-4 hover:bg-dark-900/40">
              <div className="flex items-start gap-4 min-w-0">
                <div className={cn(
                  'mt-0.5 flex items-center justify-center w-8 h-8 rounded-full shrink-0',
                  relance.status === 'scheduled' ? 'bg-amber-900/30 text-amber-400' :
                  relance.status === 'sent' ? 'bg-green-900/30 text-green-400' :
                  'bg-dark-900 text-dark-400'
                )}>
                  {CHANNEL_ICONS[relance.channel]}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium">
                      Facture #{relance.invoice_id}
                    </span>
                    <span className={cn(
                      'text-xs px-1.5 py-0.5 rounded-full',
                      relance.status === 'scheduled' ? 'bg-amber-900/40 text-amber-400' :
                      relance.status === 'sent' ? 'bg-green-900/40 text-green-400' :
                      'bg-dark-900 text-dark-500'
                    )}>
                      {relance.status === 'scheduled' ? 'En attente' :
                       relance.status === 'sent' ? 'Envoyée' : 'Annulée'}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mt-0.5 text-xs text-dark-400">
                    <span className="flex items-center gap-1">
                      {CHANNEL_ICONS[relance.channel]}
                      {CHANNEL_LABELS[relance.channel]}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {relance.status === 'sent' && relance.sent_at
                        ? `Envoyée le ${formatDate(relance.sent_at)}`
                        : `Prévue le ${formatDate(relance.scheduled_at)}`}
                    </span>
                  </div>
                  {relance.message && (
                    <p className="mt-1 text-xs text-dark-500 italic truncate max-w-xs">
                      {relance.message}
                    </p>
                  )}
                </div>
              </div>

              {relance.status === 'scheduled' && (
                <div className="flex items-center gap-2 shrink-0 ml-4">
                  <button
                    onClick={() => markSentMutation.mutate(relance.id, { onError: errHandler })}
                    disabled={markSentMutation.isPending}
                    title="Marquer comme envoyée"
                    className="flex items-center gap-1.5 text-xs bg-green-900/30 hover:bg-green-900/50 text-green-400 px-2.5 py-1.5 rounded-lg disabled:opacity-50"
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    Envoyée
                  </button>
                  <button
                    onClick={() => cancelMutation.mutate(relance.id, { onError: errHandler })}
                    disabled={cancelMutation.isPending}
                    title="Annuler la relance"
                    className="flex items-center gap-1.5 text-xs bg-dark-900 hover:bg-dark-600 text-dark-300 px-2.5 py-1.5 rounded-lg disabled:opacity-50"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    Annuler
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
