import type { ReservationDetail } from '@/types/reservation'
import type { Deposit } from '@/types/deposit'

/**
 * Source unique de vérité pour toute la logique de phase d'une réservation.
 * Toute duplication de ces règles (dans derivePhase, FocusPills, pages de phase)
 * doit être remplacée par un appel à ces fonctions.
 */

export function isDepositOk(
  reservation: Pick<ReservationDetail, 'deposit_paid'>,
  deposits: Deposit[] | undefined,
): boolean {
  if (reservation.deposit_paid) return true
  return (deposits ?? []).some((d) => d.status === 'held')
}

export function isSignatureOk(
  reservation: Pick<ReservationDetail, 'signature_url'>,
): boolean {
  return !!reservation.signature_url
}

/**
 * Vérifie si l'acompte est encaissé (paid_amount_cents >= advance attendu).
 *
 * Why: nouveau guard backend ajouté 2026-04-26 — la livraison est bloquée si
 * l'acompte n'est pas payé. L'UI doit refléter cet état pour ne pas laisser
 * l'utilisateur cliquer un CTA qui retournera 422.
 */
export function isAdvancePaid(
  reservation: Pick<ReservationDetail, 'advance_payment_amount_cents' | 'paid_amount_cents'>,
): boolean {
  const required = reservation.advance_payment_amount_cents ?? 0
  if (required <= 0) return true
  const paid = reservation.paid_amount_cents ?? 0
  return paid >= required
}

export function isReadyForDelivery(
  reservation: Pick<ReservationDetail, 'status' | 'deposit_paid' | 'signature_url'>,
  deposits: Deposit[] | undefined,
): boolean {
  if (reservation.status !== 'confirmed') return false
  return isDepositOk(reservation, deposits) && isSignatureOk(reservation)
}

export function isTerminal(
  reservation: Pick<ReservationDetail, 'status'>,
): boolean {
  return reservation.status === 'completed' || reservation.status === 'cancelled'
}

export function canCloseReservation(
  reservation: Pick<ReservationDetail, 'status'>,
): boolean {
  return reservation.status === 'returned'
}

export function canExtendReservation(
  reservation: Pick<ReservationDetail, 'status'>,
): boolean {
  return reservation.status === 'delivered' || reservation.status === 'extended'
}

export function hasLines(
  reservation: Pick<ReservationDetail, 'lines'>,
): boolean {
  return !!reservation.lines && reservation.lines.length > 0
}
