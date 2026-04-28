import { useParams } from '@tanstack/react-router'
import { useReservationFull, useReservationDeposits } from '@/api/queries'
import { derivePhase } from '../ReservationRouter'
import type { ReservationPhase } from '@/types/reservation'

/**
 * Hook central pour les pages de réservation. Charge en un seul appel la réservation
 * complète (incluant risks, pre_check_items, extensions) via useReservationFull,
 * plus les dépôts, et expose la phase dérivée.
 *
 * Utilisation :
 *   const { reservation, deposits, phase, isLoading } = useCurrentReservation()
 *
 * TanStack Query déduplique les appels : si plusieurs composants de la même page
 * l'utilisent, un seul fetch réseau est effectué.
 */
export function useCurrentReservation() {
  const { id } = useParams({ strict: false }) as { id: string }
  const reservationId = Number(id)

  const reservationQuery = useReservationFull(reservationId)
  const depositsQuery = useReservationDeposits(reservationId)

  const reservation = reservationQuery.data
  const deposits = depositsQuery.data ?? []

  const phase: ReservationPhase | null = reservation
    ? derivePhase(reservation, deposits)
    : null

  return {
    reservationId,
    reservation,
    deposits,
    phase,
    isLoading: reservationQuery.isLoading || depositsQuery.isLoading,
    error: reservationQuery.error || depositsQuery.error,
  }
}
