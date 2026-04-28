import { Link } from '@tanstack/react-router'
import { normalizeError } from '@shared/errors/normalizer'
import { useMovementDetail, useCompleteMovement } from '@/api/queries'
import { Modal } from '@shared/components/ui/Modal'
import { ActionError } from '@shared/components/ui/ActionError'
import { formatDate, formatCents, cn } from '@/lib/utils'
import {
  MOVEMENT_STATUS_LABELS as STATUS_LABELS,
  MOVEMENT_STATUS_COLORS as STATUS_COLORS,
  MOVEMENT_TYPE_LABELS as TYPE_LABELS,
  DELIVERY_METHOD_LABELS as DELIVERY_LABELS,
  INSPECTION_STATUS_LABELS as INSPECTION_LABELS,
  ITEM_CONDITION_LABELS as CONDITION_LABELS,
  ITEM_CONDITION_COLORS as CONDITION_COLORS,
  STOCK_ITEM_STATUS_LABELS as STOCK_STATUS_LABELS,
  STOCK_ITEM_STATUS_COLORS as STOCK_STATUS_COLORS,
} from '@/lib/constants'
import {
  Calendar,
  Truck,
  Package,
  Check,
  MapPin,
  ClipboardCheck,
  ArrowUpFromLine,
  ArrowDownToLine,
  History,
} from 'lucide-react'
import type {
  MovementStatus,
  MovementType,
  DeliveryMethod,
  InspectionStatus,
  ItemCondition,
} from '@/types/inventory'

interface MovementDetailModalProps {
  isOpen: boolean
  onClose: () => void
  movementId?: number
  onOpenItemHistory?: (productId: number, itemId: number) => void
}

export function MovementDetailModal({ isOpen, onClose, movementId, onOpenItemHistory }: MovementDetailModalProps) {
  const { data: movement, isLoading } = useMovementDetail(isOpen && movementId ? movementId : null)
  const completeMutation = useCompleteMovement()

  const TypeIcon = movement?.movement_type === 'return' ? ArrowDownToLine : ArrowUpFromLine

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Details du mouvement"
      size="lg"
    >
      {isLoading ? (
        <div className="space-y-4 animate-pulse">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-4">
              <div className="w-8 h-8 skel rounded-lg" />
              <div className="h-4 skel rounded w-36" />
            </div>
            <div className="h-6 skel rounded w-20" />
          </div>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex justify-between py-2 border-b border-dark-600">
              <div className="h-3 skel rounded w-24" />
              <div className="h-3 skel rounded w-32" />
            </div>
          ))}
          <div className="card divide-y divide-dark-600">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-4 py-4">
                <div className="flex-1 space-y-2">
                  <div className="h-3 skel rounded w-40" />
                  <div className="h-2 skel rounded w-24" />
                </div>
                <div className="h-3 skel rounded w-8 shrink-0" />
              </div>
            ))}
          </div>
        </div>
      ) : movement ? (
        <div className="space-y-6">
          {/* Header info */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-4">
              <TypeIcon className={cn(
                'w-5 h-5',
                movement.movement_type === 'departure' ? 'text-orange-400' : 'text-blue-400'
              )} />
              <span className="font-mono text-lg text-primary-400">
                Mouvement #{movement.id}
              </span>
              <span
                className={cn(
                  'inline-flex items-center px-2 py-1 rounded text-xs',
                  STATUS_COLORS[movement.status]
                )}
              >
                {STATUS_LABELS[movement.status]}
              </span>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              {(movement.status === 'scheduled' || movement.status === 'in_transit') && !movement.reservation_id && (
                <button
                  onClick={() => completeMutation.mutate(movement.id)}
                  disabled={completeMutation.isPending}
                  className="btn-primary btn-sm flex items-center gap-1"
                >
                  <Check className="w-3 h-3" />
                  Completer
                </button>
              )}
              {movement.reservation_id && (movement.status === 'scheduled' || movement.status === 'in_transit') && (
                <span className="text-xs text-dark-400 italic">
                  Géré via Opérations
                </span>
              )}
            </div>
          </div>

          <ActionError
            message={completeMutation.error ? (normalizeError(completeMutation.error).message || 'Une erreur est survenue') : null}
            onDismiss={() => completeMutation.reset()}
          />

          {/* Info grid */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-dark-400">Type</label>
              <p className="font-medium mt-1">
                {TYPE_LABELS[movement.movement_type]}
              </p>
            </div>

            <div>
              <label className="text-sm text-dark-400">Date prevue</label>
              <div className="flex items-center gap-2 mt-1">
                <Calendar className="w-4 h-4 text-dark-400" />
                <span>{formatDate(movement.scheduled_date)}</span>
              </div>
            </div>

            {movement.actual_date && (
              <div>
                <label className="text-sm text-dark-400">Date effective</label>
                <div className="flex items-center gap-2 mt-1">
                  <Calendar className="w-4 h-4 text-green-400" />
                  <span>{formatDate(movement.actual_date)}</span>
                </div>
              </div>
            )}

            {movement.delivery_method && (
              <div>
                <label className="text-sm text-dark-400">Methode de livraison</label>
                <div className="flex items-center gap-2 mt-1">
                  <Truck className="w-4 h-4 text-dark-400" />
                  <span>{DELIVERY_LABELS[movement.delivery_method]}</span>
                </div>
              </div>
            )}

            {movement.delivery_address && (
              <div className="col-span-2">
                <label className="text-sm text-dark-400">Adresse de livraison</label>
                <div className="flex items-center gap-2 mt-1">
                  <MapPin className="w-4 h-4 text-dark-400" />
                  <span>{movement.delivery_address}</span>
                </div>
              </div>
            )}

            {movement.inspection_status && (
              <div>
                <label className="text-sm text-dark-400">Inspection</label>
                <div className="flex items-center gap-2 mt-1">
                  <ClipboardCheck className="w-4 h-4 text-dark-400" />
                  <span>{INSPECTION_LABELS[movement.inspection_status]}</span>
                </div>
              </div>
            )}

            {movement.damage_fee > 0 && (
              <div>
                <label className="text-sm text-dark-400">Frais de dommages</label>
                <p className="font-medium mt-1 text-red-400">
                  {formatCents(movement.damage_fee)}
                </p>
              </div>
            )}
          </div>

          {/* Notes */}
          {movement.delivery_notes && (
            <div className="border-t border-dark-600 pt-4">
              <label className="text-sm text-dark-400">Notes de livraison</label>
              <p className="text-sm mt-1">{movement.delivery_notes}</p>
            </div>
          )}

          {movement.inspection_notes && (
            <div className="border-t border-dark-600 pt-4">
              <label className="text-sm text-dark-400">Notes d'inspection</label>
              <p className="text-sm mt-1">{movement.inspection_notes}</p>
            </div>
          )}

          {/* Items */}
          <div className="border-t border-dark-600 pt-4">
            <h3 className="font-medium flex items-center gap-2 mb-4">
              <Package className="w-4 h-4" />
              References ({movement.items?.length || 0})
            </h3>
            {movement.items && movement.items.length > 0 ? (
              <div className="space-y-2">
                {movement.items.map((item) => (
                  <div
                    key={item.id}
                    className="p-4 card"
                  >
                    <div className="flex justify-between items-center">
                      <div className="flex gap-3 items-center">
                        <div className="w-12 h-12 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
                          {item.product_image_url ? (
                            <img src={item.product_image_url} alt={item.product_name ?? `Produit #${item.product_id}`} className="w-full h-full object-cover" loading="lazy" />
                          ) : (
                            <Package className="w-5 h-5 text-dark-600" />
                          )}
                        </div>
                        <div>
                          {item.product_name ? (
                            <Link to={`/catalogue/products/${item.product_id}` as never} className="font-medium text-primary-400 hover:underline">
                              {item.product_name}
                            </Link>
                          ) : item.product_id ? (
                            <Link to={`/catalogue/products/${item.product_id}` as never} className="font-medium text-primary-400 hover:underline">
                              Produit #{item.product_id}
                            </Link>
                          ) : (
                            <span className="font-medium">Article #{item.event_item_id ?? item.id}</span>
                          )}
                          {item.variant_id && (
                            <span className="text-sm text-dark-400 ml-2">
                              (variante #{item.variant_id})
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm">
                          <span className="text-dark-400">Attendu: </span>
                          <span className="font-medium">{item.quantity_expected}</span>
                        </div>
                        {item.quantity_actual !== undefined && item.quantity_actual !== null && (
                          <div className="text-sm">
                            <span className="text-dark-400">Reel: </span>
                            <span className={cn(
                              'font-medium',
                              item.quantity_actual < item.quantity_expected
                                ? 'text-red-400'
                                : 'text-green-400'
                            )}>
                              {item.quantity_actual}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                    {item.condition && (
                      <div className="mt-2 text-sm">
                        <span className="text-dark-400">Etat: </span>
                        <span className={CONDITION_COLORS[item.condition]}>
                          {CONDITION_LABELS[item.condition]}
                        </span>
                        {item.condition_notes && (
                          <span className="text-dark-500 ml-2">
                            — {item.condition_notes}
                          </span>
                        )}
                      </div>
                    )}
                    {/* Unités physiques */}
                    {item.units && item.units.length > 0 && (
                      <div className="mt-4 space-y-1">
                        <p className="text-xs text-dark-500 uppercase tracking-wide">Unités physiques</p>
                        {item.units.map((unit) => (
                          <div
                            key={unit.id}
                            className="flex items-center justify-between py-1 px-2 bg-dark-900 rounded text-xs"
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-dark-400">#{unit.stock_item_id}</span>
                              {unit.status_before && unit.status_after && (
                                <span className="text-dark-500">
                                  <span className={cn('px-1 rounded', STOCK_STATUS_COLORS[unit.status_before] || '')}>
                                    {STOCK_STATUS_LABELS[unit.status_before] || unit.status_before}
                                  </span>
                                  {' → '}
                                  <span className={cn('px-1 rounded', STOCK_STATUS_COLORS[unit.status_after] || '')}>
                                    {STOCK_STATUS_LABELS[unit.status_after] || unit.status_after}
                                  </span>
                                </span>
                              )}
                              {unit.condition && (
                                <span className={CONDITION_COLORS[unit.condition as ItemCondition]}>
                                  {CONDITION_LABELS[unit.condition as ItemCondition]}
                                </span>
                              )}
                            </div>
                            {onOpenItemHistory && item.product_id && (
                              <button
                                onClick={() => onOpenItemHistory(item.product_id!, unit.stock_item_id)}
                                className="text-dark-400 hover:text-primary-400 flex items-center gap-1"
                              >
                                <History className="w-3 h-3" />
                                Historique
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 border border-dashed border-dark-600 rounded-lg">
                <Package className="w-10 h-10 text-dark-600 mx-auto mb-2" />
                <p className="text-sm text-dark-400">Aucune reference</p>
              </div>
            )}
          </div>

          {/* Timestamps */}
          <div className="border-t border-dark-600 pt-4 flex gap-6 text-xs text-dark-500">
            <span>Cree le {formatDate(movement.created_at)}</span>
            <span>Modifie le {formatDate(movement.updated_at)}</span>
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-dark-400">Mouvement introuvable</div>
      )}
    </Modal>
  )
}
