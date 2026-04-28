import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import {
  ShoppingCart,
  Plus,
  CheckCircle,
  XCircle,
  Clock,
  PackageCheck,
  Package,
  ChevronRight,
} from 'lucide-react'
import { useSupplierOrders, useSupplierOrder } from '@/api/queries/useSupplierOrders'
import { useSuppliers } from '@/api/queries/useSuppliers'
import { formatDate, formatCents } from '@/lib/utils'
import type { SupplierOrderStatus, SupplierOrderListItem } from '@/types/supplier_order'
import { CreateOrderModal } from './components/CreateOrderModal'
import { OrderDetailModal } from './components/OrderDetailModal'

// ── Statuts ────────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<SupplierOrderStatus, string> = {
  draft: 'Brouillon',
  ordered: 'Commandé',
  partially_received: 'Partiellement reçu',
  fully_received: 'Reçu',
  cancelled: 'Annulé',
}

const STATUS_COLORS: Record<SupplierOrderStatus, string> = {
  draft: 'bg-dark-900 text-dark-300 border-dark-600',
  ordered: 'bg-primary-500/10 text-primary-400 border-primary-500/20',
  partially_received: 'bg-amber-900/20 text-amber-400 border-amber-700/30',
  fully_received: 'bg-green-900/20 text-green-400 border-green-700/30',
  cancelled: 'bg-red-900/20 text-red-400 border-red-700/30',
}

const STATUS_ICONS: Record<SupplierOrderStatus, React.ReactNode> = {
  draft: <Clock className="w-3.5 h-3.5" />,
  ordered: <Package className="w-3.5 h-3.5" />,
  partially_received: <PackageCheck className="w-3.5 h-3.5" />,
  fully_received: <CheckCircle className="w-3.5 h-3.5" />,
  cancelled: <XCircle className="w-3.5 h-3.5" />,
}

function StatusBadge({ status }: { status: SupplierOrderStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${STATUS_COLORS[status]}`}
    >
      {STATUS_ICONS[status]}
      {STATUS_LABELS[status]}
    </span>
  )
}

// ── Filtres ────────────────────────────────────────────────────────────────

const STATUS_FILTERS: Array<{ value: string; label: string }> = [
  { value: '', label: 'Toutes' },
  { value: 'draft', label: 'Brouillons' },
  { value: 'ordered', label: 'Commandées' },
  { value: 'partially_received', label: 'En cours' },
  { value: 'fully_received', label: 'Reçues' },
  { value: 'cancelled', label: 'Annulées' },
]

// ── Page ───────────────────────────────────────────────────────────────────

export default function SupplierOrdersPage() {
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [showCreate, setShowCreate] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const { data, isLoading } = useSupplierOrders({
    status: statusFilter || undefined,
    skip: (page - 1) * 20,
    limit: 20,
  })

  const { data: rawSuppliersData } = useSuppliers()
  const suppliersData = Array.isArray(rawSuppliersData) ? rawSuppliersData : []
  const suppliersMap = new Map(suppliersData.map((s) => [s.id, s]))

  const { data: detailData } = useSupplierOrder(selectedId ?? 0)

  const openDetail = (item: SupplierOrderListItem) => {
    setSelectedId(item.id)
    setDetailOpen(true)
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* En-tête */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-4">
          <ShoppingCart className="w-5 h-5 text-gold-400" />
          <PageHeader title="Commandes fournisseurs" subtitle={`${data?.total ?? 0} commande${(data?.total ?? 0) !== 1 ? 's' : ''}`} />
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm rounded-lg"
        >
          <Plus className="w-4 h-4" />
          Nouvelle commande
        </button>
      </div>

      {/* Filtres statut */}
      <div className="flex gap-2 flex-wrap pb-1 lg:flex-nowrap lg:overflow-x-auto">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => {
              setStatusFilter(f.value)
              setPage(1)
            }}
            className={`px-4 py-1.5 rounded-full text-sm whitespace-nowrap transition-colors border ${
              statusFilter === f.value
                ? 'bg-gold-500 border-gold-500 text-dark-900 font-medium'
                : 'bg-dark-900 border-dark-600 text-dark-400 hover:text-dark-100'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Liste */}
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card p-4 flex items-center gap-4">
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-36" />
                <div className="h-2 skel rounded w-52" />
              </div>
              <div className="h-5 skel rounded w-24 shrink-0" />
              <div className="h-4 skel rounded w-4 shrink-0" />
            </div>
          ))}
        </div>
      ) : !data?.items.length ? (
        <div className="card text-center py-14">
          <ShoppingCart className="w-10 h-10 mx-auto mb-4 text-dark-500" />
          <p className="font-medium">Aucune commande</p>
          <p className="text-sm text-dark-400 mt-1">
            {statusFilter ? `Aucune commande au statut "${STATUS_LABELS[statusFilter as SupplierOrderStatus] ?? statusFilter}".` : 'Créez votre première commande fournisseur.'}
          </p>
        </div>
      ) : (
        <div className="card divide-y divide-dark-600 p-0 overflow-hidden">
          {data.items.map((item) => {
            const supplier = suppliersMap.get(item.supplier_id)
            return (
              <button
                key={item.id}
                onClick={() => openDetail(item)}
                className="w-full text-left px-4 py-4 hover:bg-dark-600 transition-colors flex items-center gap-4"
              >
                <div className="w-8 h-8 bg-gold-400/10 rounded-lg flex items-center justify-center shrink-0">
                  <Package className="w-4 h-4 text-gold-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-dark-100">{item.reference}</p>
                  <p className="text-xs text-dark-400">
                    {supplier?.name ?? `Fournisseur #${item.supplier_id}`}
                  </p>
                </div>
                <div className="text-right text-xs text-dark-500 shrink-0">
                  <div>Commandé {formatDate(item.order_date)}</div>
                  {item.expected_date && (
                    <div className="text-amber-400">Livr. {formatDate(item.expected_date)}</div>
                  )}
                </div>
                <StatusBadge status={item.status} />
                <ChevronRight className="w-4 h-4 text-dark-500 shrink-0" />
              </button>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {data && Math.ceil((data.total ?? 0) / 20) > 1 && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-1.5 text-sm border border-dark-600 rounded-lg disabled:opacity-40 hover:bg-dark-600 text-dark-300"
          >
            Précédent
          </button>
          <span className="px-4 py-1.5 text-sm text-dark-400">
            {page} / {Math.ceil((data.total ?? 0) / 20)}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(Math.ceil((data.total ?? 0) / 20), p + 1))}
            disabled={page === Math.ceil((data.total ?? 0) / 20)}
            className="px-4 py-1.5 text-sm border border-dark-600 rounded-lg disabled:opacity-40 hover:bg-dark-600 text-dark-300"
          >
            Suivant
          </button>
        </div>
      )}

      {/* Modals */}
      <CreateOrderModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        suppliers={suppliersData ?? []}
      />
      <OrderDetailModal
        order={detailData ?? null}
        isOpen={detailOpen}
        onClose={() => {
          setDetailOpen(false)
          setSelectedId(null)
        }}
      />
    </div>
  )
}
