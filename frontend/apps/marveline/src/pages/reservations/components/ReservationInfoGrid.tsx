import { ArrowUpFromLine, Calendar, ArrowDownToLine, Package, Weight, Truck } from 'lucide-react'
import { formatDate } from '@/lib/utils'
import type { ReservationDetail } from '@/types/reservation'

const DELIVERY_METHOD_LABELS: Record<string, string> = {
  self: 'Livraison propre',
  carrier: 'Transporteur',
  pickup: 'Retrait client',
}

interface ReservationInfoGridProps {
  reservation: Pick<ReservationDetail,
    'delivery_date' | 'event_date' | 'return_date' | 'lines' |
    'total_weight_kg' | 'delivery_method' | 'delivery_fee_cents' | 'carrier_name'
  >
}

export function ReservationInfoGrid({ reservation }: ReservationInfoGridProps) {
  const cells = [
    { icon: ArrowUpFromLine, label: 'Livraison', value: formatDate(reservation.delivery_date) },
    { icon: Calendar, label: 'Événement', value: formatDate(reservation.event_date) },
    { icon: ArrowDownToLine, label: 'Retour', value: formatDate(reservation.return_date) },
    { icon: Package, label: 'Articles', value: `${reservation.lines?.length ?? 0} ligne${(reservation.lines?.length ?? 0) !== 1 ? 's' : ''}` },
  ]

  // Logistique cells (only if data present)
  if (reservation.total_weight_kg != null) {
    cells.push({
      icon: Weight,
      label: 'Poids total',
      value: `${reservation.total_weight_kg.toFixed(1)} kg`,
    })
  }

  if (reservation.delivery_method) {
    const methodLabel = DELIVERY_METHOD_LABELS[reservation.delivery_method] ?? reservation.delivery_method
    const feeLabel = reservation.delivery_fee_cents
      ? ` · ${(reservation.delivery_fee_cents / 100).toFixed(2)} €`
      : ''
    const carrierLabel = reservation.carrier_name ? ` (${reservation.carrier_name})` : ''
    cells.push({
      icon: Truck,
      label: 'Transport',
      value: `${methodLabel}${carrierLabel}${feeLabel}`,
    })
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
      {cells.map((c) => (
        <div key={c.label} className="bg-dark-900/60 rounded-lg p-4">
          <div className="text-xs text-dark-500 mb-1 flex items-center gap-1">
            <c.icon className="w-3 h-3" />{c.label}
          </div>
          <div className="text-sm font-medium">{c.value}</div>
        </div>
      ))}
    </div>
  )
}
