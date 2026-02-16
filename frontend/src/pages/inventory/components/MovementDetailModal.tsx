import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { inventoryApi } from '@/api/inventory'
import { Modal } from '@/components/ui/Modal'
import { formatDate } from '@/lib/utils'
import { cn } from '@/lib/utils'
import {
  Calendar,
  Truck,
  Package,
  Check,
  MapPin,
  ClipboardCheck,
  ArrowUpFromLine,
  ArrowDownToLine,
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
}

const STATUS_LABELS: Record<MovementStatus, string> = {
  scheduled: 'Planifie',
  in_transit: 'En transit',
  completed: 'Termine',
  late: 'En retard',
  cancelled: 'Annule',
}

const STATUS_COLORS: Record<MovementStatus, string> = {
  scheduled: 'bg-blue-500/10 text-blue-500',
  in_transit: 'bg-orange-500/10 text-orange-500',
  completed: 'bg-green-500/10 text-green-500',
  late: 'bg-red-500/10 text-red-500',
  cancelled: 'bg-dark-700 text-dark-300',
}

const TYPE_LABELS: Record<MovementType, string> = {
  departure: 'Depart',
  return: 'Retour',
}

const DELIVERY_LABELS: Record<DeliveryMethod, string> = {
  delivery: 'Livraison',
  pickup: 'Enlevement',
  shipping: 'Expedition',
}

const INSPECTION_LABELS: Record<InspectionStatus, string> = {
  pending: 'En attente',
  ok: 'OK',
  damaged: 'Endommage',
  missing: 'Manquant',
}

const CONDITION_LABELS: Record<ItemCondition, string> = {
  perfect: 'Parfait',
  good: 'Bon',
  damaged: 'Endommage',
  missing: 'Manquant',
}

const CONDITION_COLORS: Record<ItemCondition, string> = {
  perfect: 'text-green-500',
  good: 'text-blue-400',
  damaged: 'text-orange-500',
  missing: 'text-red-500',
}

export function MovementDetailModal({ isOpen, onClose, movementId }: MovementDetailModalProps) {
  const queryClient = useQueryClient()

  const { data: movement, isLoading } = useQuery({
    queryKey: ['inventory-movement', movementId],
    queryFn: () => inventoryApi.getMovement(movementId!),
    enabled: isOpen && !!movementId,
  })

  const completeMutation = useMutation({
    mutationFn: (id: number) => inventoryApi.completeMovement(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory-movement', movementId] })
      queryClient.invalidateQueries({ queryKey: ['inventory-movements'] })
    },
  })

  const TypeIcon = movement?.movement_type === 'return' ? ArrowDownToLine : ArrowUpFromLine

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Details du mouvement"
      size="lg"
    >
      {isLoading ? (
        <div className="text-center py-8 text-dark-400">Chargement...</div>
      ) : movement ? (
        <div className="space-y-6">
          {/* Header info */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
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
              {(movement.status === 'scheduled' || movement.status === 'in_transit') && (
                <button
                  onClick={() => completeMutation.mutate(movement.id)}
                  disabled={completeMutation.isPending}
                  className="btn-primary btn-sm flex items-center gap-1"
                >
                  <Check className="w-3 h-3" />
                  Completer
                </button>
              )}
            </div>
          </div>

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
                  {(movement.damage_fee / 100).toFixed(2)} EUR
                </p>
              </div>
            )}
          </div>

          {/* Notes */}
          {movement.delivery_notes && (
            <div className="border-t border-dark-700 pt-4">
              <label className="text-sm text-dark-400">Notes de livraison</label>
              <p className="text-sm mt-1">{movement.delivery_notes}</p>
            </div>
          )}

          {movement.inspection_notes && (
            <div className="border-t border-dark-700 pt-4">
              <label className="text-sm text-dark-400">Notes d'inspection</label>
              <p className="text-sm mt-1">{movement.inspection_notes}</p>
            </div>
          )}

          {/* Items */}
          <div className="border-t border-dark-700 pt-4">
            <h3 className="font-medium flex items-center gap-2 mb-3">
              <Package className="w-4 h-4" />
              Articles ({movement.items?.length || 0})
            </h3>
            {movement.items && movement.items.length > 0 ? (
              <div className="space-y-2">
                {movement.items.map((item) => (
                  <div
                    key={item.id}
                    className="p-3 bg-dark-800 rounded-lg border border-dark-700"
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <span className="font-medium">
                          {item.product_id
                            ? `Produit #${item.product_id}`
                            : `Article evenement #${item.event_item_id}`}
                        </span>
                        {item.product_variation_id && (
                          <span className="text-sm text-dark-400 ml-2">
                            (variation #{item.product_variation_id})
                          </span>
                        )}
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
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 border border-dashed border-dark-700 rounded-lg">
                <Package className="w-10 h-10 text-dark-600 mx-auto mb-2" />
                <p className="text-sm text-dark-400">Aucun article</p>
              </div>
            )}
          </div>

          {/* Timestamps */}
          <div className="border-t border-dark-700 pt-4 flex gap-6 text-xs text-dark-500">
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
