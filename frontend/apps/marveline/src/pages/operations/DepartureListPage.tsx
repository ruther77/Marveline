import { PageHeader } from '@/components/PageHeader'
import { Link } from '@tanstack/react-router'
import { Truck, ArrowLeft, QrCode } from 'lucide-react'
import { useOperationsSummary } from '@/api/queries/useOperations'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { DomainStatusBadge } from '@shared/components/ui'
import { formatDate } from '@/lib/utils'
import type { OperationsSummaryItem } from '@/api/operations'

function DepartureCard({ item }: { item: OperationsSummaryItem }) {
  return (
    <Link
      to="/operations/departure/$reservationId"
      params={{ reservationId: String(item.id) }}
      className="flex items-center gap-4 p-4 card border border-dark-600 hover:border-blue-500/30 transition-colors"
    >
      <Truck className="w-5 h-5 text-blue-400 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{item.reference}</p>
        <p className="text-xs text-dark-400 truncate">
          {item.customer_name}
          {item.delivery_date && ` · Livraison : ${formatDate(item.delivery_date)}`}
        </p>
      </div>
      <DomainStatusBadge status={item.status} />
    </Link>
  )
}

export default function DepartureListPage() {
  const { data, isLoading, error, refetch } = useOperationsSummary()
  const departures = data?.departures ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link to="/operations" className="p-2 hover:bg-dark-600 rounded-lg">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="flex items-center gap-2">
            <Truck className="w-5 h-5 text-blue-400" />
            <PageHeader title="Départs à préparer" />
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

      {error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-2 animate-pulse">
          {[1, 2, 3, 4].map((i) => (
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
      ) : departures.length === 0 ? (
        <div className="text-center py-16 text-dark-500">
          <Truck className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="font-medium">Aucun départ à préparer</p>
          <p className="text-sm mt-1">Les réservations confirmées avec livraison prévue apparaîtront ici.</p>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-dark-400">{departures.length} réservation{departures.length > 1 ? 's' : ''}</p>
          {departures.map((r) => (
            <DepartureCard key={r.id} item={r} />
          ))}
        </div>
      )}
    </div>
  )
}
