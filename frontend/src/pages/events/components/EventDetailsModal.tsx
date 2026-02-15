import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reservationsApi } from '@/api/reservations'
import { Modal } from '@/components/ui/Modal'
import { formatDate } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { Calendar, MapPin, Package, Check, XCircle, Banknote } from 'lucide-react'
import type { ReservationStatus } from '@/types/reservation'

interface ReservationDetailsModalProps {
  isOpen: boolean
  onClose: () => void
  reservationId?: number
}

const STATUS_LABELS: Record<ReservationStatus, string> = {
  draft: 'Brouillon',
  confirmed: 'Confirmee',
  delivered: 'Livree',
  returned: 'Retournee',
  cancelled: 'Annulee',
}

const STATUS_COLORS: Record<ReservationStatus, string> = {
  draft: 'bg-dark-700 text-dark-300',
  confirmed: 'bg-blue-500/10 text-blue-500',
  delivered: 'bg-orange-500/10 text-orange-500',
  returned: 'bg-green-500/10 text-green-500',
  cancelled: 'bg-red-500/10 text-red-500',
}

export function ReservationDetailsModal({ isOpen, onClose, reservationId }: ReservationDetailsModalProps) {
  const queryClient = useQueryClient()

  const { data: reservation, isLoading } = useQuery({
    queryKey: ['reservation', reservationId],
    queryFn: () => reservationsApi.getReservation(reservationId!),
    enabled: isOpen && !!reservationId,
  })

  const confirmMutation = useMutation({
    mutationFn: (id: number) => reservationsApi.confirmReservation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reservation', reservationId] })
      queryClient.invalidateQueries({ queryKey: ['reservations'] })
    },
  })

  const cancelMutation = useMutation({
    mutationFn: (id: number) => reservationsApi.cancelReservation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reservation', reservationId] })
      queryClient.invalidateQueries({ queryKey: ['reservations'] })
    },
  })

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Details de la reservation"
      size="lg"
    >
      {isLoading ? (
        <div className="text-center py-8 text-dark-400">Chargement...</div>
      ) : reservation ? (
        <div className="space-y-6">
          {/* Header info */}
          <div className="flex items-center justify-between">
            <div>
              <span className="font-mono text-lg text-primary-400">
                {reservation.reference}
              </span>
              <span
                className={cn(
                  'ml-3 inline-flex items-center px-2 py-1 rounded text-xs',
                  STATUS_COLORS[reservation.status]
                )}
              >
                {STATUS_LABELS[reservation.status]}
              </span>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              {reservation.status === 'draft' && (
                <button
                  onClick={() => confirmMutation.mutate(reservation.id)}
                  disabled={confirmMutation.isPending}
                  className="btn-primary btn-sm flex items-center gap-1"
                >
                  <Check className="w-3 h-3" />
                  Confirmer
                </button>
              )}
              {(reservation.status === 'draft' || reservation.status === 'confirmed') && (
                <button
                  onClick={() => cancelMutation.mutate(reservation.id)}
                  disabled={cancelMutation.isPending}
                  className="btn-secondary btn-sm flex items-center gap-1 text-red-400 hover:text-red-300"
                >
                  <XCircle className="w-3 h-3" />
                  Annuler
                </button>
              )}
            </div>
          </div>

          {/* Client */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-dark-400">Client</label>
              {reservation.customer ? (
                <div className="mt-1">
                  <p className="font-medium">{reservation.customer.display_name}</p>
                  <p className="text-sm text-dark-400">{reservation.customer.email}</p>
                  {reservation.customer.phone && (
                    <p className="text-sm text-dark-400">{reservation.customer.phone}</p>
                  )}
                </div>
              ) : (
                <p className="font-medium mt-1">Client #{reservation.customer_id}</p>
              )}
            </div>

            <div>
              <label className="text-sm text-dark-400">Date evenement</label>
              <div className="flex items-center gap-2 mt-1">
                <Calendar className="w-4 h-4 text-dark-400" />
                <span>{formatDate(reservation.event_date)}</span>
              </div>
            </div>

            <div>
              <label className="text-sm text-dark-400">Livraison</label>
              <div className="flex items-center gap-2 mt-1">
                <Calendar className="w-4 h-4 text-blue-400" />
                <span>{formatDate(reservation.delivery_date)}</span>
              </div>
            </div>

            <div>
              <label className="text-sm text-dark-400">Retour</label>
              <div className="flex items-center gap-2 mt-1">
                <Calendar className="w-4 h-4 text-orange-400" />
                <span>{formatDate(reservation.return_date)}</span>
              </div>
            </div>

            {reservation.event_location && (
              <div className="col-span-2">
                <label className="text-sm text-dark-400">Lieu</label>
                <div className="flex items-center gap-2 mt-1">
                  <MapPin className="w-4 h-4 text-dark-400" />
                  <span>{reservation.event_location}</span>
                </div>
              </div>
            )}

            {reservation.rental_days > 0 && (
              <div>
                <label className="text-sm text-dark-400">Duree location</label>
                <p className="font-medium mt-1">{reservation.rental_days} jour{reservation.rental_days > 1 ? 's' : ''}</p>
              </div>
            )}
          </div>

          {/* Lines */}
          <div className="border-t border-dark-700 pt-4">
            <h3 className="font-medium flex items-center gap-2 mb-3">
              <Package className="w-4 h-4" />
              Produits ({reservation.lines?.length || 0})
            </h3>
            {reservation.lines && reservation.lines.length > 0 ? (
              <div className="space-y-2">
                {reservation.lines.map((line) => (
                  <div key={line.id} className="p-3 bg-dark-800 rounded-lg border border-dark-700">
                    <div className="flex justify-between items-center">
                      <div>
                        <span className="font-medium">
                          {line.product?.name || `Produit #${line.product_id}`}
                        </span>
                        <span className="text-sm text-dark-400 ml-2">
                          x{line.quantity}
                        </span>
                      </div>
                      <div className="text-right">
                        <div className="text-sm text-dark-400">
                          {Number(line.unit_price_euros).toFixed(2)} EUR/u
                        </div>
                        <div className="font-medium text-green-500">
                          {Number(line.subtotal_euros).toFixed(2)} EUR
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 border border-dashed border-dark-700 rounded-lg">
                <Package className="w-10 h-10 text-dark-600 mx-auto mb-2" />
                <p className="text-sm text-dark-400">Aucun produit</p>
              </div>
            )}
          </div>

          {/* Totals */}
          <div className="border-t border-dark-700 pt-4 space-y-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2 text-dark-300">
                <Banknote className="w-4 h-4" />
                <span>Depot</span>
              </div>
              <div className="text-right">
                <span className="font-medium">
                  {Number(reservation.deposit_amount_euros || 0).toFixed(2)} EUR
                </span>
                <span className={cn(
                  'ml-2 text-xs px-2 py-0.5 rounded',
                  reservation.deposit_paid
                    ? 'bg-green-500/10 text-green-500'
                    : 'bg-red-500/10 text-red-500'
                )}>
                  {reservation.deposit_paid ? 'Paye' : 'Non paye'}
                </span>
              </div>
            </div>

            <div className="flex justify-between items-center text-lg font-bold border-t border-dark-700 pt-2">
              <span>Total</span>
              <span className="text-green-500">
                {Number(reservation.total_amount_euros).toFixed(2)} EUR
              </span>
            </div>
          </div>

          {/* Notes */}
          {reservation.notes && (
            <div className="border-t border-dark-700 pt-4">
              <label className="text-sm text-dark-400">Notes</label>
              <p className="text-sm mt-1">{reservation.notes}</p>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-8 text-dark-400">Reservation introuvable</div>
      )}
    </Modal>
  )
}
