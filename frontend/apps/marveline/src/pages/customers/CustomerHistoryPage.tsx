import { PageHeader } from '@/components/PageHeader'
import { Link, useParams } from '@tanstack/react-router'
import { useCustomerHistory } from '@/api/queries/useCustomers'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents } from '@/lib/utils'
import { CalendarDays, FileText, TrendingUp } from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'

const RESERVATION_STATUS_LABELS: Record<string, string> = {
  draft: 'Brouillon',
  confirmed: 'Confirmée',
  confirmed_risk: 'Risque',
  pre_check: 'Pré-check',
  delivered: 'Livrée',
  extended: 'Prolongée',
  returned: 'Retournée',
  returned_dispute: 'Retournée (litige)',
  completed: 'Terminée',
  cancelled: 'Annulée',
}

const INVOICE_STATUS_LABELS: Record<string, string> = {
  draft: 'Brouillon',
  sent: 'Envoyée',
  paid: 'Payée',
  partially_paid: 'Partielle',
  overdue: 'En retard',
  cancelled: 'Annulée',
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'text-green-400',
  paid: 'text-green-400',
  confirmed: 'text-primary-400',
  pre_check: 'text-primary-400',
  delivered: 'text-blue-400',
  extended: 'text-blue-400',
  sent: 'text-amber-400',
  partially_paid: 'text-amber-400',
  overdue: 'text-red-400',
  cancelled: 'text-dark-500',
  draft: 'text-dark-400',
}

export default function CustomerHistoryPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const customerId = Number(id)

  const { data: history, isLoading, error } = useCustomerHistory(customerId)

  // ── Loading skeleton ───────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <div className="h-8 w-48 skel rounded animate-pulse" />
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="card p-4 space-y-2">
              <div className="h-4 w-20 skel rounded animate-pulse" />
              <div className="h-6 w-12 skel rounded animate-pulse" />
            </div>
          ))}
        </div>
        <div className="card p-6 space-y-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-10 skel rounded animate-pulse" />
          ))}
        </div>
        <div className="card p-6 space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-10 skel rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  // ── Error / not found ──────────────────────────────────────────────────────
  if (error || !history) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="card p-8 text-center text-danger">
          {error ? normalizeError(error).message : 'Client introuvable'}
        </div>
      </div>
    )
  }

  const { customer, reservations, invoices, stats } = history
  const displayName = customer.display_name

  // ── Main view ──────────────────────────────────────────────────────────────
  return (
    <div className="max-w-3xl mx-auto space-y-4 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <BackButton label="Retour" />
        <div className="flex-1 min-w-0">
          <PageHeader title="Historique client" subtitle={displayName} />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="flex items-center gap-2 text-dark-400 text-xs mb-1">
            <CalendarDays className="w-3.5 h-3.5" />
            Réservations
          </div>
          <p className="text-2xl font-bold">{stats.total_reservations}</p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 text-dark-400 text-xs mb-1">
            <TrendingUp className="w-3.5 h-3.5" />
            CA total
          </div>
          <p className="text-2xl font-bold text-primary-400">
            {formatCents(stats.total_revenue_cents)}
          </p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 text-dark-400 text-xs mb-1">
            <FileText className="w-3.5 h-3.5" />
            Dernier événement
          </div>
          <p className="text-base font-semibold">
            {stats.last_event_date
              ? new Date(stats.last_event_date).toLocaleDateString('fr-FR')
              : '—'}
          </p>
        </div>
      </div>

      {/* Réservations */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">
          Réservations ({reservations.length})
        </h2>
        {reservations.length === 0 ? (
          <p className="text-sm text-dark-400 text-center py-6">Aucune réservation</p>
        ) : (
          <div className="space-y-1">
            {reservations.map(r => (
              <Link
                key={r.id}
                to="/reservations/$id/phases"
                params={{ id: String(r.id) }}
                className="flex items-center justify-between py-2.5 px-2 rounded-lg hover:bg-dark-600 transition-colors group min-h-[44px]"
              >
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-dark-200 group-hover:text-dark-50 transition-colors">
                    {r.reference}
                  </span>
                  <span className="text-xs text-dark-500 ml-2">
                    {r.event_date
                      ? new Date(r.event_date).toLocaleDateString('fr-FR')
                      : '—'}
                  </span>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <span className={`text-xs font-medium ${STATUS_COLORS[r.status] ?? 'text-dark-400'}`}>
                    {RESERVATION_STATUS_LABELS[r.status] ?? r.status}
                  </span>
                  <span className="text-sm font-medium">
                    {formatCents(r.total_amount_cents)}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Factures */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">
          Factures ({invoices.length})
        </h2>
        {invoices.length === 0 ? (
          <p className="text-sm text-dark-400 text-center py-6">Aucune facture</p>
        ) : (
          <div className="space-y-1">
            {invoices.map(inv => (
              <Link
                key={inv.id}
                to="/finance/invoices/$id"
                params={{ id: String(inv.id) }}
                className="flex items-center justify-between py-2.5 px-2 rounded-lg hover:bg-dark-600 transition-colors group min-h-[44px]"
              >
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-dark-200 group-hover:text-dark-50 transition-colors">
                    {inv.invoice_number}
                  </span>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <span className={`text-xs font-medium ${STATUS_COLORS[inv.status] ?? 'text-dark-400'}`}>
                    {INVOICE_STATUS_LABELS[inv.status] ?? inv.status}
                  </span>
                  <div className="text-right">
                    <span className="text-sm font-medium">
                      {formatCents(inv.paid_amount_cents)}
                    </span>
                    <span className="text-xs text-dark-500 ml-1">
                      / {formatCents(inv.total_amount_cents)}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
