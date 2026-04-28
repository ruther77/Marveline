import { Link } from '@tanstack/react-router'
import { formatDate } from '@/lib/utils'
import { formatCents } from '@/lib/utils'
import type { DevisDetailFull } from '@/types/devis'
import { Truck, Package, Users, FileCheck } from 'lucide-react'

const DELIVERY_METHOD_CONFIG: Record<string, { label: string; icon: typeof Truck }> = {
  self: { label: 'Livraison propre', icon: Truck },
  carrier: { label: 'Transporteur', icon: Package },
  pickup: { label: 'Retrait client', icon: Users },
}

interface DevisInfoCardProps {
  devis: DevisDetailFull
}

export function DevisInfoCard({ devis }: DevisInfoCardProps) {
  const deliveryConfig = devis.delivery_method
    ? DELIVERY_METHOD_CONFIG[devis.delivery_method]
    : null

  return (
    <div className="card grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
      <div>
        <p className="text-dark-400">Client</p>
        <p className="font-medium">{devis.customer_name}</p>
      </div>
      <div>
        <p className="text-dark-400">Date evenement</p>
        <p className="">{formatDate(devis.event_date)}</p>
      </div>
      <div>
        <p className="text-dark-400">Validite</p>
        <p className="">jusqu'au {formatDate(devis.valid_until)}</p>
      </div>
      {devis.event_location && (
        <div>
          <p className="text-dark-400">Lieu</p>
          <p className="">{devis.event_location}</p>
        </div>
      )}

      {/* Delivery info */}
      {deliveryConfig && (
        <div>
          <p className="text-dark-400">Livraison</p>
          <div className="flex items-center gap-1.5">
            <deliveryConfig.icon className="w-3.5 h-3.5 text-primary-400" />
            <span>{deliveryConfig.label}</span>
            {devis.carrier_name && (
              <span className="text-dark-400">({devis.carrier_name})</span>
            )}
          </div>
        </div>
      )}
      {devis.delivery_fee_cents != null && devis.delivery_fee_cents > 0 && (
        <div>
          <p className="text-dark-400">Frais livraison</p>
          <p className="font-medium text-primary-400">{formatCents(devis.delivery_fee_cents)}</p>
        </div>
      )}
      {devis.delivery_address && (
        <div className="col-span-2 md:col-span-3">
          <p className="text-dark-400">Adresse livraison</p>
          <p className="">
            {devis.delivery_address}
            {devis.delivery_postal_code && `, ${devis.delivery_postal_code}`}
            {devis.delivery_city && ` ${devis.delivery_city}`}
          </p>
        </div>
      )}
      {devis.delivery_instructions && (
        <div className="col-span-2 md:col-span-3">
          <p className="text-dark-400">Instructions livraison</p>
          <p className="">{devis.delivery_instructions}</p>
        </div>
      )}

      {devis.notes && (
        <div className="col-span-2 md:col-span-3">
          <p className="text-dark-400">Notes</p>
          <p className="">{devis.notes}</p>
        </div>
      )}

      {devis.converted_reservation_id && devis.converted_reservation_reference && (
        <div className="col-span-2 md:col-span-3">
          <p className="text-dark-400">Réservation liée</p>
          <Link
            to="/reservations/$id"
            params={{ id: String(devis.converted_reservation_id) }}
            className="inline-flex items-center gap-1.5 text-primary-400 hover:text-primary-300 font-medium"
          >
            <FileCheck className="w-3.5 h-3.5" />
            {devis.converted_reservation_reference}
          </Link>
        </div>
      )}
    </div>
  )
}
