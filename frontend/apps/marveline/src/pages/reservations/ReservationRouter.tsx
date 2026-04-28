import type { ReservationDetail, ReservationPhase } from '@/types/reservation'
import type { Deposit } from '@/types/deposit'
import { hasLines, isReadyForDelivery } from './selectors/reservationPhase'

export type { ReservationPhase }

export function derivePhase(reservation: ReservationDetail, deposits: Deposit[]): ReservationPhase {
  const { status } = reservation

  if (status === 'cancelled') return 'annulee'
  if (status === 'completed') return 'terminee'
  if (status === 'returned_dispute') return 'litige'
  if (status === 'returned') return 'retournee'
  if (status === 'extended') return 'prolongee'
  if (status === 'delivered') return 'en-cours'
  if (status === 'confirmed_risk') return 'risque'
  if (status === 'pre_check') return 'precheck'

  if (status === 'confirmed') {
    return isReadyForDelivery(reservation, deposits) ? 'prete' : 'legal'
  }

  return hasLines(reservation) ? 'brouillon' : 'brouillon-incomplet'
}

/**
 * Ce composant sert de point d'entree pour /reservations/$id/ (index).
 * La logique de navigation par phase est dans EventIdLayout (layout parent)
 * qui reste monte pendant les transitions entre phases.
 */
export default function ReservationRouter() {
  return null
}
