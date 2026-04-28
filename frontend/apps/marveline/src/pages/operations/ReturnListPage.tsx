import { PageHeader } from '@/components/PageHeader'
import { Link } from '@tanstack/react-router'
import { RotateCcw, ArrowLeft, QrCode, AlertTriangle } from 'lucide-react'
import { useOperationsSummary } from '@/api/queries/useOperations'
import { DomainStatusBadge } from '@shared/components/ui'
import { formatDate } from '@/lib/utils'
import type { OperationsSummaryItem } from '@/api/operations'

function ReturnCard({ item, overdue }: { item: OperationsSummaryItem; overdue?: boolean }) {
  return (
    <Link
      to="/operations/return/$reservationId"
      params={{ reservationId: String(item.id) }}
      className={`flex items-center gap-4 p-4 card border transition-colors ${
        overdue ? 'border-red-500/30 hover:border-red-400/50 bg-red-900/10' : 'border-dark-600 hover:border-orange-500/30'
      }`}
    >
      {overdue
        ? <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
        : <RotateCcw className="w-5 h-5 text-orange-400 shrink-0" />
      }
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{item.reference}</p>
        <p className="text-xs text-dark-400 truncate">
          {item.customer_name}
          {item.return_date && ` · Retour : ${formatDate(item.return_date)}`}
        </p>
      </div>
      <DomainStatusBadge status={item.status} />
    </Link>
  )
}

export default function ReturnListPage() {
  const { data, isLoading } = useOperationsSummary()
  const returnsPending = data?.returns_pending ?? []
  const returnsOverdue = data?.returns_overdue ?? []
  const total = returnsPending.length + returnsOverdue.length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link to="/operations" className="p-2 hover:bg-dark-600 rounded-lg">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="flex items-center gap-2">
            <RotateCcw className="w-5 h-5 text-orange-400" />
            <PageHeader title="Retours attendus" />
          </div>
        </div>
        <Link
          to="/operations/scan"
          className="flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white text-sm font-semibold px-4 py-2 rounded-lg"
        >
          <QrCode className="w-4 h-4" />
          Scanner
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-6 animate-pulse">
          <div className="space-y-2">
            <div className="h-4 bg-dark-800 rounded w-36 mb-3" />
            {[1, 2, 3].map(i => (
              <div key={i} className="flex items-center gap-4 p-4 card border border-dark-700">
                <div className="w-5 h-5 bg-dark-800 rounded shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-3.5 bg-dark-800 rounded w-28" />
                  <div className="h-2.5 bg-dark-800 rounded w-48" />
                </div>
                <div className="h-5 w-20 bg-dark-800 rounded-full" />
              </div>
            ))}
          </div>
        </div>
      ) : total === 0 ? (
        <div className="text-center py-16 text-dark-500">
          <RotateCcw className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="font-medium">Aucun retour attendu</p>
          <p className="text-sm mt-1">Les réservations livrées en attente de retour apparaîtront ici.</p>
        </div>
      ) : (
        <>
          {returnsOverdue.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-red-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                En retard ({returnsOverdue.length})
              </h2>
              <div className="space-y-2">
                {returnsOverdue.map((r) => (
                  <ReturnCard key={r.id} item={r} overdue />
                ))}
              </div>
            </section>
          )}

          <section>
            <h2 className="text-sm font-semibold text-dark-300 mb-3 flex items-center gap-2">
              <RotateCcw className="w-4 h-4" />
              Retours attendus ({returnsPending.length})
            </h2>
            {returnsPending.length === 0 ? (
              <p className="text-sm text-dark-500 text-center py-4">Aucun retour en attente</p>
            ) : (
              <div className="space-y-2">
                {returnsPending.map((r) => (
                  <ReturnCard key={r.id} item={r} />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}
