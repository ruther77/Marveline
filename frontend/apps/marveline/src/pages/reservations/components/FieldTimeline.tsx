import { formatDate, cn } from '@/lib/utils'
import type { ReservationDetail, ReservationStatus } from '@/types/reservation'

interface Movement {
  id: number
  movement_type: string
  status: string
  scheduled_date: string
}

interface FieldTimelineProps {
  reservation: Pick<ReservationDetail, 'status' | 'created_at' | 'delivery_date' | 'event_date' | 'return_date'>
  movements?: Movement[]
}

export function FieldTimeline({ reservation, movements = [] }: FieldTimelineProps) {
  const depMv = movements.find((m) => m.movement_type === 'departure')
  const retMv = movements.find((m) => m.movement_type === 'return')

  const DONE_STATUSES: ReservationStatus[] = ['delivered', 'extended', 'returned', 'returned_dispute', 'completed']
  const isDelivered = DONE_STATUSES.includes(reservation.status as ReservationStatus)
  const isReturned = (['returned', 'returned_dispute', 'completed'] as string[]).includes(reservation.status)
  const isCompleted = reservation.status === 'completed'

  const steps = [
    {
      label: 'Réservation créée',
      date: reservation.created_at,
      done: true,
      color: 'bg-green-500',
    },
    {
      label: 'Livraison / Départ matériel',
      date: depMv?.scheduled_date || reservation.delivery_date,
      done: isDelivered,
      color: isDelivered ? 'bg-green-500' : 'bg-dark-600',
      note: depMv ? `Mvt #${depMv.id} — ${depMv.status}` : undefined,
    },
    {
      label: 'Événement',
      date: reservation.event_date,
      done: isDelivered,
      color: isDelivered ? 'bg-green-500' : 'bg-dark-600',
    },
    {
      label: 'Retour prévu',
      date: retMv?.scheduled_date || reservation.return_date,
      done: isReturned,
      color: isReturned ? 'bg-green-500' : retMv ? 'bg-amber-500' : 'bg-dark-600',
      note: retMv ? `Mvt #${retMv.id} — ${retMv.status}` : undefined,
    },
    {
      label: 'Clôture',
      date: undefined,
      done: isCompleted,
      color: isCompleted ? 'bg-green-500' : 'bg-dark-600',
    },
  ]

  return (
    <div>
      <ol className="relative ml-2 border-l border-dark-600 space-y-4">
        {steps.map((s, i) => (
          <li key={i} className="ml-6">
            <span className={cn('absolute -left-[9px] w-4 h-4 rounded-full border-2 border-dark-900', s.color)} />
            <p className={cn('text-sm font-medium', s.done ? 'text-white' : 'text-dark-500')}>{s.label}</p>
            {s.date && <p className="text-xs text-dark-400">{formatDate(s.date)}</p>}
            {s.note && <p className="text-xs text-dark-500">{s.note}</p>}
          </li>
        ))}
      </ol>
    </div>
  )
}
