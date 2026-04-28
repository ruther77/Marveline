import { PageHeader } from '@/components/PageHeader'
import { Link } from '@tanstack/react-router'
import { QrCode, Truck, RotateCcw, AlertTriangle } from 'lucide-react'
import { useOperationsSummary } from '@/api/queries/useOperations'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { DomainStatusBadge } from '@shared/components/ui'
import { formatDate } from '@/lib/utils'
import type { OperationsSummaryItem } from '@/api/operations'

function OpCard({ item, icon, accent }: { item: OperationsSummaryItem; icon: React.ReactNode; accent: string }) {
  return (
    <Link
      to="/reservations/$id"
      params={{ id: String(item.id) }}
      className={`flex items-center gap-4 p-4 card border transition-colors ${accent}`}
    >
      {icon}
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

export default function OperationsDashboardPage() {
  const { data, isLoading, error, refetch } = useOperationsSummary()

  const departures = data?.departures ?? []
  const returnsPending = data?.returns_pending ?? []
  const returnsOverdue = data?.returns_overdue ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Opérations" />
        <Link
          to="/operations/scan"
          className="flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white text-sm font-semibold px-4 py-2 rounded-lg"
        >
          <QrCode className="w-4 h-4" />
          Scanner QR
        </Link>
      </div>

      {error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-6 animate-pulse">
          {/* Départs section */}
          <div className="space-y-2">
            <div className="h-4 bg-dark-800 rounded w-40 mb-3" />
            {[1, 2].map(i => (
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
          {/* Retours section */}
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
      ) : (
        <>
          <section>
            <Link to="/operations/departure" className="text-sm font-semibold text-dark-300 mb-3 flex items-center gap-2 hover:text-dark-100 transition-colors">
              <Truck className="w-4 h-4" />
              Départs à préparer ({departures.length})
            </Link>
            {departures.length === 0 ? (
              <div className="text-center py-8 text-dark-500">
                <Truck className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">Aucun départ à préparer</p>
              </div>
            ) : (
              <div className="space-y-2">
                {departures.map((r) => (
                  <OpCard key={r.id} item={r} icon={<Truck className="w-5 h-5 text-blue-400 shrink-0" />} accent="border-dark-600 hover:border-blue-500/30" />
                ))}
              </div>
            )}
          </section>

          <section>
            <Link to="/operations/return" className="text-sm font-semibold text-dark-300 mb-3 flex items-center gap-2 hover:text-dark-100 transition-colors">
              <RotateCcw className="w-4 h-4" />
              Retours attendus ({returnsPending.length})
            </Link>
            {returnsPending.length === 0 ? (
              <div className="text-center py-8 text-dark-500">
                <RotateCcw className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">Aucun retour attendu</p>
              </div>
            ) : (
              <div className="space-y-2">
                {returnsPending.map((r) => (
                  <OpCard key={r.id} item={r} icon={<RotateCcw className="w-5 h-5 text-orange-400 shrink-0" />} accent="border-dark-600 hover:border-orange-500/30" />
                ))}
              </div>
            )}
          </section>

          {returnsOverdue.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-red-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                En retard ({returnsOverdue.length})
              </h2>
              <div className="space-y-2">
                {returnsOverdue.map((r) => (
                  <OpCard key={r.id} item={r} icon={<AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />} accent="border-red-500/30 hover:border-red-400/50 bg-red-900/10" />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
