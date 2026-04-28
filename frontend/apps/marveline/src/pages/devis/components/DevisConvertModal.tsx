import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Modal } from '@shared/components/ui'
import { useDevisMutations } from '@/api/queries/useDevis'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents } from '@/lib/utils'
import { Truck, Package, Users } from 'lucide-react'
import type { DevisDeliveryMethod } from '@/types/devis'

const DELIVERY_METHOD_LABELS: Record<string, { label: string; icon: typeof Truck }> = {
  self: { label: 'Livraison propre', icon: Truck },
  carrier: { label: 'Transporteur', icon: Package },
  pickup: { label: 'Retrait client', icon: Users },
}

interface Props {
  devisId: number
  reference: string
  open: boolean
  onClose: () => void
  deliveryDate: string
  returnDate: string
  eventDate?: string | null
  eventLocation?: string
  // Delivery info from devis
  deliveryMethod?: DevisDeliveryMethod | null
  deliveryFeeCents?: number
  carrierName?: string | null
  carrierCode?: string | null
  deliveryAddress?: string | null
  deliveryCity?: string | null
  deliveryPostalCode?: string | null
  deliveryZoneId?: number | null
  deliveryInstructions?: string | null
}

export function DevisConvertModal({
  devisId,
  reference,
  open,
  onClose,
  deliveryDate,
  returnDate,
  eventDate: initialEventDate,
  eventLocation: initialEventLocation,
  deliveryMethod,
  deliveryFeeCents,
  carrierName,
  carrierCode,
  deliveryAddress,
  deliveryCity,
  deliveryPostalCode,
  deliveryZoneId,
  deliveryInstructions,
}: Props) {
  const today = new Date().toISOString().split('T')[0]
  const [eventDate, setEventDate] = useState(initialEventDate?.slice(0, 10) || today)
  const [deliveryDate_, setDeliveryDate] = useState(deliveryDate)
  const [returnDate_, setReturnDate] = useState(returnDate)
  const [eventLocation, setEventLocation] = useState(initialEventLocation ?? '')
  const [error, setError] = useState<string | null>(null)
  const { convertToReservation } = useDevisMutations()
  const navigate = useNavigate()

  const deliveryConfig = deliveryMethod ? DELIVERY_METHOD_LABELS[deliveryMethod] : null

  const handleConfirm = () => {
    if (!eventLocation.trim()) {
      setError('Le lieu de l\'evenement est requis.')
      return
    }
    setError(null)
    convertToReservation.mutate(
      {
        id: devisId,
        payload: {
          event_date: eventDate,
          delivery_date: deliveryDate_,
          return_date: returnDate_,
          event_location: eventLocation.trim(),
          // Propagate delivery info
          delivery_method: deliveryMethod || undefined,
          delivery_fee_cents: deliveryFeeCents || undefined,
          carrier_name: carrierName || undefined,
          carrier_code: carrierCode || undefined,
          delivery_address: deliveryAddress || undefined,
          delivery_city: deliveryCity || undefined,
          delivery_postal_code: deliveryPostalCode || undefined,
          delivery_zone_id: deliveryZoneId || undefined,
          delivery_instructions: deliveryInstructions || undefined,
        },
      },
      {
        onSuccess: (data) => {
          onClose()
          navigate({ to: '/reservations/$id', params: { id: String(data.reservation_id) } })
        },
        onError: (err) => {
          setError(
            normalizeError(err).message ||
              'Erreur lors de la conversion.'
          )
        },
      }
    )
  }

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Convertir en reservation"
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={onClose} className="text-sm text-dark-400 hover:text-dark-50 px-4 py-2">
            Annuler
          </button>
          <button
            onClick={handleConfirm}
            disabled={convertToReservation.isPending}
            className="bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-6 py-2 rounded-lg disabled:opacity-60"
          >
            {convertToReservation.isPending ? 'Conversion…' : 'Convertir'}
          </button>
        </div>
      }
    >
      <p className="text-dark-300 text-sm mb-4">
        Le devis <span className="font-medium">{reference}</span> sera converti en reservation.
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-xs text-dark-400 mb-1">Date de l'evenement *</label>
          <input
            type="date"
            value={eventDate}
            onChange={(e) => setEventDate(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-xs text-dark-400 mb-1">Date de livraison *</label>
          <input
            type="date"
            value={deliveryDate_}
            onChange={(e) => setDeliveryDate(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-xs text-dark-400 mb-1">Date de retour *</label>
          <input
            type="date"
            value={returnDate_}
            onChange={(e) => setReturnDate(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-xs text-dark-400 mb-1">Lieu de l'evenement *</label>
          <input
            type="text"
            value={eventLocation}
            onChange={(e) => setEventLocation(e.target.value)}
            placeholder="Ex: Salle des fetes, Paris 75001"
            className="input"
          />
        </div>

        {/* Delivery info recap (read-only, from devis) */}
        {deliveryConfig && (
          <div className="border-t border-dark-600 pt-4 space-y-2">
            <p className="text-xs text-dark-500 font-medium uppercase tracking-wide">Livraison (depuis le devis)</p>
            <div className="flex items-center gap-2 bg-dark-900/40 rounded-lg p-3">
              <deliveryConfig.icon className="w-4 h-4 text-primary-400 shrink-0" />
              <div className="text-sm">
                <span className="text-dark-200">{deliveryConfig.label}</span>
                {carrierName && <span className="text-dark-400 ml-1">({carrierName})</span>}
                {deliveryFeeCents != null && deliveryFeeCents > 0 && (
                  <span className="ml-2 text-primary-400 font-medium">{formatCents(deliveryFeeCents)}</span>
                )}
              </div>
            </div>
            {deliveryAddress && (
              <p className="text-xs text-dark-400">
                {deliveryAddress}{deliveryPostalCode ? `, ${deliveryPostalCode}` : ''}{deliveryCity ? ` ${deliveryCity}` : ''}
              </p>
            )}
          </div>
        )}
      </div>

      {error && <p className="text-red-400 text-sm mt-4">{error}</p>}
    </Modal>
  )
}
