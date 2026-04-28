import { Link } from '@tanstack/react-router'
import { formatDate } from '@/lib/utils'

interface LinkedReservation {
  id: number
  reference: string
  customer_name?: string
  event_date: string
}

interface InvoiceLinkedReservationProps {
  reservation: LinkedReservation
}

export function InvoiceLinkedReservation({ reservation }: InvoiceLinkedReservationProps) {
  return (
    <div className="border-t border-dark-600 pt-4">
      <label className="text-sm text-dark-400">Réservation liée</label>
      <div className="mt-2 p-4 card">
        <div className="flex justify-between items-center">
          <div>
            <Link to={`/reservations/${reservation.id}` as never} className="font-mono text-sm text-primary-400 hover:underline">
              {reservation.reference}
            </Link>
            {reservation.customer_name && (
              <span className="text-sm text-dark-300 ml-4">
                {reservation.customer_name}
              </span>
            )}
          </div>
          <span className="text-sm text-dark-400">
            {formatDate(reservation.event_date)}
          </span>
        </div>
      </div>
    </div>
  )
}
