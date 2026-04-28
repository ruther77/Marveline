import { PageHeader } from '@/components/PageHeader'
import { useParams } from '@tanstack/react-router'
import { useProductDetail, useProductStock } from '@/api/queries'
import { formatCents } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { RefreshCw, QrCode, Package } from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import { Link } from '@tanstack/react-router'

const STATE_CONFIG: Record<string, { label: string; color: string; bg: string; dot: string }> = {
  available:   { label: 'Disponible',    color: 'text-green-400',  bg: 'bg-green-500/10 border-green-500/30', dot: 'bg-green-400' },
  reserved:    { label: 'Réservé',       color: 'text-blue-400',   bg: 'bg-blue-500/10 border-blue-500/30',   dot: 'bg-blue-400' },
  on_location: { label: 'En location',   color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/30', dot: 'bg-orange-400' },
  damaged:     { label: 'Endommagé',     color: 'text-red-400',    bg: 'bg-red-500/10 border-red-500/30',     dot: 'bg-red-400' },
  in_repair:   { label: 'En réparation', color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/30', dot: 'bg-yellow-400' },
  retired:     { label: 'Retiré',        color: 'text-dark-400',   bg: 'bg-dark-900 border-dark-600',         dot: 'bg-dark-400' },
}

// Labels pour le filtre pills
const FILTER_OPTIONS = [
  { key: 'all', label: 'Tous' },
  { key: 'available', label: 'Disponibles' },
  { key: 'damaged', label: 'Endommagés' },
  { key: 'in_repair', label: 'Réparation' },
  { key: 'reserved', label: 'Réservés' },
  { key: 'on_location', label: 'En location' },
  { key: 'retired', label: 'Retirés' },
]

import { useState } from 'react'
import type { StockItem } from '@/types/stock_item'

export default function ProductStatesPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const productId = Number(id)
  const [filter, setFilter] = useState<string>('all')

  const { data: stockDetail, isLoading, error, refetch } = useProductStock(
    !isNaN(productId) ? productId : null
  )

  const { data: product } = useProductDetail(productId)

  const kpi = stockDetail
    ? [
        { key: 'available',   label: 'Disponible',    value: stockDetail.qty_available },
        { key: 'damaged',     label: 'Endommagé',     value: stockDetail.qty_damaged },
        { key: 'in_repair',   label: 'Réparation',    value: stockDetail.qty_in_repair },
        { key: 'on_location', label: 'En location',   value: stockDetail.qty_on_location },
        { key: 'reserved',    label: 'Réservé',       value: stockDetail.qty_reserved },
        { key: 'retired',     label: 'Retiré',        value: stockDetail.qty_retired },
      ]
    : []

  const items: StockItem[] = stockDetail?.items ?? []
  const filtered = filter === 'all' ? items : items.filter((i) => i.status === filter)

  if (error) {
    return <ErrorState onRetry={() => refetch()} />
  }

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <div className="h-8 skel rounded animate-pulse w-48" />
        <div className="grid grid-cols-2 sm:grid-cols-3 sm:grid-cols-6 gap-4">
          {[...Array(6)].map((_, i) => <div key={i} className="h-16 bg-dark-900 rounded-xl animate-pulse" />)}
        </div>
        {[...Array(4)].map((_, i) => <div key={i} className="h-12 bg-dark-900 rounded-xl animate-pulse" />)}
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <BackButton />
        <div className="w-14 h-14 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
          {product?.image_url ? (
            <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" loading="lazy" />
          ) : (
            <Package className="w-5 h-5 text-dark-600" />
          )}
        </div>
        <div>
          <PageHeader title="États matériel" />
          {product && <p className="text-sm text-dark-400">{product.name}</p>}
        </div>
        <div className="ml-auto flex items-center gap-4">
          {stockDetail && (
            <span className="text-sm text-dark-400">
              Total : <span className="font-semibold">{stockDetail.total}</span> unités
            </span>
          )}
          <button
            onClick={() => refetch()}
            className="p-2 rounded-lg hover:bg-dark-600 transition-colors text-dark-400 hover:text-dark-100"
            title="Actualiser"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* KPI grid */}
      {stockDetail && (
        <div className="grid grid-cols-2 sm:grid-cols-3 sm:grid-cols-6 gap-2 mb-6">
          {kpi.map((k) => {
            const cfg = STATE_CONFIG[k.key]
            return (
              <button
                key={k.key}
                onClick={() => setFilter(k.key)}
                className={cn(
                  'flex flex-col items-center p-4 rounded-xl border text-center transition-all',
                  filter === k.key ? cfg.bg : 'card hover:bg-dark-600'
                )}
              >
                <span className={cn('text-xl font-bold', filter === k.key ? cfg.color : '')}>
                  {k.value}
                </span>
                <span className="text-xs text-dark-400 mt-0.5">{k.label}</span>
              </button>
            )
          })}
        </div>
      )}

      {/* Filter pills */}
      <div className="flex gap-2 flex-wrap mb-4">
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setFilter(opt.key)}
            className={cn(
              'px-4 py-1 rounded-full text-xs font-medium border transition-colors',
              filter === opt.key
                ? 'bg-primary-500 text-white border-primary-500'
                : 'card text-dark-400 hover:bg-dark-600'
            )}
          >
            {opt.label}
            {opt.key !== 'all' && stockDetail && (
              <span className="ml-1 opacity-60">
                ({items.filter((i) => i.status === opt.key).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Items list */}
      {filtered.length === 0 ? (
        <div className="space-y-3">
          <div className="text-center py-12 text-dark-400 text-sm">Aucun article dans cet état</div>
          {stockDetail && stockDetail.total > 0 && items.length === 0 && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300">
              Le produit a un stock agrégé, mais aucun suivi unitaire n&apos;est encore initialisé.
              Les compteurs proviennent donc de `stock_quantity` et `available_quantity`.
            </div>
          )}
        </div>
      ) : (
        <div className="card p-0 overflow-hidden divide-y divide-dark-600">
          {filtered.map((item) => {
            const cfg = STATE_CONFIG[item.status] ?? STATE_CONFIG.available
            return (
              <div key={item.id} className="flex items-center gap-4 px-4 py-4">
                <div className={cn('w-2 h-2 rounded-full shrink-0', cfg.dot)} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">
                    {item.serial_number ? `N° ${item.serial_number}` : `Article #${item.id}`}
                  </p>
                  {item.notes && <p className="text-xs text-dark-400 truncate">{item.notes}</p>}
                  {item.current_reservation_id && (
                    <p className="text-xs text-dark-400">
                      Réservation #{item.current_reservation_id}
                    </p>
                  )}
                </div>
                <span
                  className={cn(
                    'text-xs px-2 py-0.5 rounded-full border font-medium',
                    cfg.bg,
                    cfg.color
                  )}
                >
                  {cfg.label}
                </span>
                <Link
                  to="/stock/items/$id"
                  params={{ id: `${productId}-${item.id}` }}
                  className="text-xs font-medium text-primary-400 hover:text-primary-300"
                >
                  Voir unité
                </Link>
              </div>
            )
          })}
        </div>
      )}

      {/* Cycle de remise en stock */}
      {stockDetail && (stockDetail.qty_damaged > 0 || stockDetail.qty_in_repair > 0) && (
        <div className="mt-6 card p-4">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <RefreshCw className="w-4 h-4 text-primary-400" />
            Cycle de remise en stock
          </h3>
          <div className="flex items-center gap-2 text-xs">
            <div className="flex-1 text-center bg-orange-500/10 border border-orange-500/30 rounded-lg p-2">
              <p className="font-semibold text-orange-400">{stockDetail.qty_damaged}</p>
              <p className="text-dark-400 mt-0.5">Retour</p>
            </div>
            <span className="text-dark-400">→</span>
            <div className="flex-1 text-center bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-2">
              <p className="font-semibold text-yellow-400">{stockDetail.qty_in_repair}</p>
              <p className="text-dark-400 mt-0.5">Traitement</p>
            </div>
            <span className="text-dark-400">→</span>
            <div className="flex-1 text-center bg-green-500/10 border border-green-500/30 rounded-lg p-2">
              <p className="font-semibold text-green-400">{stockDetail.qty_available}</p>
              <p className="text-dark-400 mt-0.5">Réintégration</p>
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-4 mt-6">
        <Link
          to="/catalogue/products/$id/photos"
          params={{ id: String(productId) }}
          className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg border border-dark-600 hover:bg-dark-600 transition-colors"
        >
          Ajouter média
        </Link>
        <Link
          to="/catalogue/qr"
          className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-primary-500 text-white hover:bg-primary-500/90 transition-colors"
        >
          <QrCode className="w-4 h-4" />
          Contrôle QR
        </Link>
      </div>
    </div>
  )
}
