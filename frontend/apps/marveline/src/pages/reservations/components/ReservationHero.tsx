import { Calendar, MapPin, Check, FileText, User, Receipt } from 'lucide-react'
import { formatDate, formatCents, cn } from '@/lib/utils'
import {
  RESERVATION_STATUS_LABELS as STATUS_LABELS,
  RESERVATION_STATUS_COLORS as STATUS_COLORS,
} from '@/lib/constants'
import type { ReservationDetail, ReservationStatus } from '@/types/reservation'
import type { Deposit } from '@/types/deposit'
import { FocusPills } from './FocusPills'
import { EntityBreadcrumb } from '@/layout/EntityBreadcrumb'
import { EntityContextBar, type EntityLink } from '@/layout/EntityContextBar'

export const HERO_BG: Record<string, string> = {
  draft: 'bg-dark-900 border-dark-600',
  confirmed: 'bg-amber-950/40 border-amber-700/40',
  confirmed_risk: 'bg-red-950/40 border-red-700/40',
  pre_check: 'bg-green-950/40 border-green-700/40',
  delivered: 'bg-blue-950/40 border-blue-700/40',
  extended: 'bg-blue-950/40 border-blue-700/40',
  returned: 'bg-orange-950/40 border-orange-700/40',
  returned_dispute: 'bg-orange-950/40 border-orange-700/40',
  completed: 'bg-purple-950/40 border-purple-700/40',
  cancelled: 'bg-dark-900 border-dark-600',
}

const PROGRESS_COLOR: Record<string, string> = {
  confirmed: 'bg-amber-500',
  pre_check: 'bg-green-500',
  delivered: 'bg-blue-500',
  extended: 'bg-blue-500',
  returned: 'bg-orange-500',
  completed: 'bg-purple-500',
}

const STATUS_ORDER: ReservationStatus[] = [
  'draft', 'confirmed', 'pre_check', 'delivered', 'returned', 'completed',
]

const STAGE_ALIAS: Record<string, ReservationStatus> = {
  confirmed_risk: 'confirmed',
  extended: 'delivered',
  returned_dispute: 'returned',
}

interface ReservationHeroProps {
  reservation: ReservationDetail
  deposit?: Deposit
  showPills?: boolean
}

export function ReservationHero({ reservation, deposit, showPills = true }: ReservationHeroProps) {
  const { status } = reservation
  const progressColor = PROGRESS_COLOR[status]

  const stage = STAGE_ALIAS[status] ?? (status as ReservationStatus)
  const idx = STATUS_ORDER.indexOf(stage)
  const pct = idx < 0 ? 0 : Math.round(((idx + 1) / STATUS_ORDER.length) * 100)

  // Liens croises vers entites liees
  const contextLinks: EntityLink[] = []
  if (reservation.customer?.display_name) {
    contextLinks.push({
      label: reservation.customer.display_name,
      href: '/customers/$id',
      params: { id: String(reservation.customer_id) },
      icon: User,
    })
  }
  if (reservation.devis_id) {
    contextLinks.push({
      label: `Devis DEV-${reservation.devis_id}`,
      href: '/devis/$id',
      params: { id: String(reservation.devis_id) },
      icon: FileText,
      color: 'blue',
    })
  }

  return (
    <div className="space-y-3">
      <EntityBreadcrumb
        items={[
          { label: 'Réservations', href: '/reservations' },
          { label: reservation.reference },
        ]}
        backTo="/reservations"
      />
      {contextLinks.length > 0 && <EntityContextBar links={contextLinks} />}
      <div className={cn('rounded-xl border p-4 space-y-4', HERO_BG[status] || 'bg-dark-900 border-dark-600')}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-base font-semibold text-primary-400">
              {reservation.reference}
            </span>
            <span className={cn('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', STATUS_COLORS[status])}>
              {STATUS_LABELS[status]}
            </span>
            {reservation.signature_url && (
              <span className="text-xs text-green-400 flex items-center gap-1 px-2 py-0.5 bg-green-900/20 rounded border border-green-700/30">
                <Check className="w-3 h-3" />Signé
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-dark-100 mt-1">
            {reservation.customer?.display_name || `Client #${reservation.customer_id}`}
          </p>
          <div className="flex items-center gap-4 mt-1 text-xs text-dark-400 flex-wrap">
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />{formatDate(reservation.event_date)}
            </span>
            {reservation.event_location && (
              <span className="flex items-center gap-1">
                <MapPin className="w-3 h-3" />{reservation.event_location}
              </span>
            )}
            {reservation.rental_days > 0 && <span>{reservation.rental_days}j de location</span>}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-lg font-bold text-white">{formatCents(reservation.total_amount_cents)}</div>
          {reservation.deposit_amount_cents > 0 && (
            <div className="text-xs text-dark-400">caution {formatCents(reservation.deposit_amount_cents)}</div>
          )}
        </div>
      </div>

      {progressColor && (
        <div className="h-1 bg-dark-900 rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all', progressColor)}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      {showPills && <FocusPills reservation={reservation} deposit={deposit} />}
    </div>
    </div>
  )
}
