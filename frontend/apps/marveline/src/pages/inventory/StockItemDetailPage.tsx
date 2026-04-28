import { useState } from 'react'
import { useParams, Link } from '@tanstack/react-router'
import { useProductsList, useProductStock, useStockItemHistory } from '@/api/queries'
import { cn, formatDate } from '@/lib/utils'
import {
  Package,
  Clock,
  ArrowRight,
  Hash,
  Calendar,
  FileText,
  Pencil,
} from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import { MOVEMENT_TYPE_LABELS, MOVEMENT_STATUS_LABELS } from '@/lib/constants'
import { StockItemStatusSheet } from '@/components/ui/StockItemStatusSheet'

const STATUS_LABELS: Record<string, string> = {
  available: 'Disponible',
  reserved: 'Réservé',
  on_location: 'En location',
  damaged: 'Endommagé',
  in_repair: 'En réparation',
  retired: 'Retiré',
}

const STATUS_COLORS: Record<string, string> = {
  available: 'bg-green-500/10 text-green-400 border-green-500/30',
  reserved: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  on_location: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
  damaged: 'bg-red-500/10 text-red-400 border-red-500/30',
  in_repair: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  retired: 'bg-dark-600 text-dark-400 border-dark-500',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-1 rounded-full text-sm font-medium border',
        STATUS_COLORS[status] || 'bg-dark-900 text-dark-400 border-dark-600'
      )}
    >
      {STATUS_LABELS[status] || status}
    </span>
  )
}

export default function StockItemDetailPage() {
  const { id } = useParams({ strict: false }) as { id: string }

  // id encodes "productId-itemId"
  const [productIdStr, itemIdStr] = id.split('-')
  const productId = Number(productIdStr)
  const itemId = Number(itemIdStr)

  const isValid = !isNaN(productId) && !isNaN(itemId)

  const { data: stockDetail, isLoading: loadingStock } = useProductStock(
    isValid ? productId : null
  )

  const { data: history, isLoading: loadingHistory } = useStockItemHistory(
    isValid ? productId : null,
    isValid ? itemId : null,
  )

  const { data: productsData } = useProductsList({ limit: 1000, active_only: false })
  const product = productsData?.items.find((p) => p.id === productId)
  const item = stockDetail?.items.find((i) => i.id === itemId)

  const isLoading = loadingStock || loadingHistory
  const currentStatus = item?.status || history?.current_status || 'unknown'
  const [isStatusSheetOpen, setIsStatusSheetOpen] = useState(false)

  if (!isValid) {
    return (
      <div className="p-6 text-center text-dark-400">
        Identifiant invalide.{' '}
        <Link to="/stock/items" className="text-primary-400 hover:underline">
          Retour au stock
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <BackButton />
        <div>
          <h1 className="text-xl font-semibold">
            Unité #{itemId}
            {history?.serial_number && (
              <span className="ml-2 text-sm font-mono text-primary-400">
                {history.serial_number}
              </span>
            )}
          </h1>
          {product && (
            <p className="text-sm text-dark-400">
              {product.name} · {product.sku}
            </p>
          )}
        </div>
        {history && (
          <button
            onClick={() => setIsStatusSheetOpen(true)}
            className="ml-auto flex items-center gap-1.5 group"
            title="Changer le statut"
          >
            <StatusBadge status={currentStatus} />
            <Pencil className="w-3.5 h-3.5 text-dark-500 group-hover:text-primary-400 transition-colors" />
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-pulse">
          <div className="space-y-4">
            <div className="card p-4 space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex justify-between">
                  <div className="h-3 skel rounded w-24" />
                  <div className="h-3 skel rounded w-32" />
                </div>
              ))}
            </div>
          </div>
          <div className="md:col-span-2 space-y-4">
            <div className="card p-4 space-y-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4">
                  <div className="w-8 h-8 skel rounded shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 skel rounded w-48" />
                    <div className="h-2 skel rounded w-32" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Left column — infos */}
          <div className="space-y-4">
            {/* Fiche item */}
            <div className="card p-4 space-y-4">
              <h2 className="text-sm font-medium text-dark-300 uppercase tracking-wide flex items-center gap-2">
                <Package className="w-4 h-4" />
                Informations
              </h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-dark-400">ID unité</span>
                  <span className="font-mono">#{itemId}</span>
                </div>
                {history?.serial_number && (
                  <div className="flex justify-between">
                    <span className="text-dark-400 flex items-center gap-1">
                      <Hash className="w-3.5 h-3.5" /> N° série
                    </span>
                    <span className="text-primary-400 font-mono">{history.serial_number}</span>
                  </div>
                )}
                <div className="flex justify-between items-center">
                  <span className="text-dark-400">Statut</span>
                  <button
                    onClick={() => setIsStatusSheetOpen(true)}
                    className="flex items-center gap-1 group"
                    title="Changer le statut"
                  >
                    <StatusBadge status={currentStatus} />
                    <Pencil className="w-3 h-3 text-dark-600 group-hover:text-primary-400 transition-colors" />
                  </button>
                </div>
                {item?.current_reservation_id && (
                  <div className="flex justify-between">
                    <span className="text-dark-400 flex items-center gap-1">
                      <FileText className="w-3.5 h-3.5" /> Réservation
                    </span>
                    <span className="">#{item.current_reservation_id}</span>
                  </div>
                )}
                {item?.notes && (
                  <div className="pt-1 border-t border-dark-600">
                    <span className="text-dark-400 block mb-1">Notes</span>
                    <p className="text-xs">{item.notes}</p>
                  </div>
                )}
                {item?.created_at && (
                  <div className="flex justify-between">
                    <span className="text-dark-400 flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5" /> Créé le
                    </span>
                    <span className="text-dark-300">{formatDate(item.created_at)}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Produit lié */}
            {product && (
              <div className="card p-4 space-y-4">
                <h2 className="text-sm font-medium text-dark-300 uppercase tracking-wide">
                  Produit associé
                </h2>
                <div className="space-y-2 text-sm">
                  {product.image_url && (
                    <img
                      src={product.image_url}
                      alt={product.name}
                      loading="lazy"
                      className="w-full h-32 object-cover rounded-lg"
                    />
                  )}
                  <p className="font-medium">{product.name}</p>
                  <p className="text-dark-400 font-mono text-xs">{product.sku}</p>
                  <Link
                    to="/catalogue/products/$id"
                    params={{ id: String(productId) }}
                    className="text-primary-400 text-xs hover:underline"
                  >
                    Voir le produit →
                  </Link>
                </div>
              </div>
            )}
          </div>

          {/* Right — historique mouvements */}
          <div className="md:col-span-2">
            <div className="card p-4 space-y-4">
              <h2 className="text-sm font-medium text-dark-300 uppercase tracking-wide flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Historique des mouvements
                {history && (
                  <span className="ml-auto text-xs text-dark-500 normal-case">
                    {history.entries.length} entrée{history.entries.length !== 1 ? 's' : ''}
                  </span>
                )}
              </h2>

              {!history || history.entries.length === 0 ? (
                <div className="text-center py-10 border border-dashed border-dark-600 rounded-lg">
                  <Clock className="w-10 h-10 text-dark-600 mx-auto mb-2" />
                  <p className="text-sm text-dark-400">Aucun mouvement enregistré</p>
                </div>
              ) : (
                <div className="relative">
                  <div className="absolute left-3 top-4 bottom-4 w-px bg-dark-900" />
                  <div className="space-y-4">
                    {history.entries.map((entry, i) => (
                      <div key={i} className="flex gap-4">
                        <div className="flex-shrink-0 w-7 flex justify-center">
                          <div
                            className={cn(
                              'w-2.5 h-2.5 rounded-full mt-1.5 border-2',
                              entry.movement_status === 'completed'
                                ? 'bg-green-500 border-green-500'
                                : entry.movement_status === 'cancelled'
                                ? 'bg-dark-600 border-dark-500'
                                : 'bg-primary-500 border-primary-500'
                            )}
                          />
                        </div>
                        <div className="flex-1 pb-4 border-b border-dark-600 last:border-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span
                              className={cn(
                                'text-xs font-medium px-1.5 py-0.5 rounded',
                                entry.movement_type === 'departure'
                                  ? 'bg-orange-500/10 text-orange-400'
                                  : 'bg-blue-500/10 text-blue-400'
                              )}
                            >
                              {MOVEMENT_TYPE_LABELS[entry.movement_type as keyof typeof MOVEMENT_TYPE_LABELS] || entry.movement_type}
                            </span>
                            <span className="text-xs text-dark-500">
                              {MOVEMENT_STATUS_LABELS[entry.movement_status as keyof typeof MOVEMENT_STATUS_LABELS] || entry.movement_status}
                            </span>
                            <span className="text-xs text-dark-500 ml-auto">
                              {formatDate(entry.scheduled_date)}
                            </span>
                          </div>

                          {(entry.status_before || entry.status_after) && (
                            <div className="flex items-center gap-2 mt-2">
                              {entry.status_before && (
                                <span
                                  className={cn(
                                    'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border',
                                    STATUS_COLORS[entry.status_before] || 'bg-dark-900 text-dark-400 border-dark-600'
                                  )}
                                >
                                  {STATUS_LABELS[entry.status_before] || entry.status_before}
                                </span>
                              )}
                              <ArrowRight className="w-3.5 h-3.5 text-dark-500 flex-shrink-0" />
                              {entry.status_after && (
                                <span
                                  className={cn(
                                    'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border',
                                    STATUS_COLORS[entry.status_after] || 'bg-dark-900 text-dark-400 border-dark-600'
                                  )}
                                >
                                  {STATUS_LABELS[entry.status_after] || entry.status_after}
                                </span>
                              )}
                            </div>
                          )}

                          {entry.condition && (
                            <p className="text-xs text-dark-400 mt-1">
                              État:{' '}
                              <span className="">{entry.condition}</span>
                              {entry.condition_notes && (
                                <span className="text-dark-500"> — {entry.condition_notes}</span>
                              )}
                            </p>
                          )}

                          {entry.actual_date && entry.actual_date !== entry.scheduled_date && (
                            <p className="text-xs text-dark-500 mt-0.5">
                              Effectué le {formatDate(entry.actual_date)}
                            </p>
                          )}

                          {entry.reservation_id && (
                            <p className="text-xs text-dark-500 mt-0.5">
                              Réservation #{entry.reservation_id}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {isValid && (
        <StockItemStatusSheet
          isOpen={isStatusSheetOpen}
          onClose={() => setIsStatusSheetOpen(false)}
          productId={productId}
          itemId={itemId}
          currentStatus={currentStatus as 'available' | 'reserved' | 'on_location' | 'damaged' | 'in_repair' | 'retired'}
          itemLabel={history?.serial_number ?? `Unité #${itemId}`}
        />
      )}
    </div>
  )
}
