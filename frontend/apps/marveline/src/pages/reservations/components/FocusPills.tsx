import { formatDate, formatCents, cn } from '@/lib/utils'
import type { ReservationDetail } from '@/types/reservation'
import type { Deposit } from '@/types/deposit'

interface FocusPillsProps {
  reservation: ReservationDetail
  deposit?: Deposit
}

export function FocusPills({ reservation, deposit }: FocusPillsProps) {
  const { status } = reservation
  const depositHeld = deposit?.status === 'held' || reservation.deposit_paid
  const pills: { label: string; value: string; color?: string }[] = []

  const paid = reservation.paid_amount_cents ?? 0
  const total = reservation.total_amount_cents
  const remaining = Math.max(total - paid, 0)
  const isFullyPaid = remaining === 0 && total > 0
  const hasPartialPayment = paid > 0 && remaining > 0

  if (status === 'draft') {
    pills.push({ label: 'Statut', value: 'Brouillon ouvert' })
    pills.push({ label: 'Articles', value: `${reservation.lines?.length ?? 0} ligne${(reservation.lines?.length ?? 0) !== 1 ? 's' : ''}` })
    const hasLines = (reservation.lines?.length ?? 0) > 0
    pills.push({ label: 'Prochaine étape', value: hasLines ? 'Confirmer la réservation' : 'Ajouter des articles' })
  } else if (['confirmed', 'confirmed_risk', 'pre_check'].includes(status)) {
    pills.push({ label: 'Date événement', value: formatDate(reservation.event_date) })
    pills.push({ label: 'Stock', value: 'Réservé', color: 'text-green-400' })
    const cautionAmt = reservation.deposit_amount_cents
    if (cautionAmt > 0) {
      pills.push({
        label: 'Caution',
        value: depositHeld ? `${formatCents(cautionAmt)} encaissée` : `${formatCents(cautionAmt)} en attente`,
        color: depositHeld ? 'text-green-400' : 'text-amber-400',
      })
    }
    if (isFullyPaid) {
      pills.push({ label: 'Paiement', value: 'Soldée', color: 'text-green-400' })
    } else if (hasPartialPayment) {
      pills.push({ label: 'Solde restant', value: formatCents(remaining), color: 'text-amber-400' })
    } else {
      pills.push({ label: 'À régler', value: formatCents(total), color: 'text-amber-400' })
    }
  } else if (status === 'delivered' || status === 'extended') {
    pills.push({ label: 'Sorti le', value: formatDate(reservation.delivery_date) })
    pills.push({ label: 'Retour prévu', value: formatDate(reservation.return_date), color: 'text-amber-400' })
    pills.push({ label: 'Caution', value: depositHeld ? 'Encaissée' : 'En attente', color: depositHeld ? 'text-green-400' : 'text-red-400' })
    if (isFullyPaid) {
      pills.push({ label: 'Paiement', value: 'Soldée', color: 'text-green-400' })
    } else {
      pills.push({ label: 'Solde restant', value: formatCents(remaining), color: 'text-red-400' })
    }
  } else if (status === 'returned' || status === 'returned_dispute') {
    pills.push({ label: 'Retour effectué', value: formatDate(reservation.return_date) })
    const depositLabel =
      deposit?.status === 'released' ? 'Restituée'
      : deposit?.status === 'retained' ? 'Retenue'
      : deposit?.status === 'held' ? 'Encaissée'
      : 'N/A'
    const depositColor =
      deposit?.status === 'released' ? 'text-green-400'
      : deposit?.status === 'retained' ? 'text-amber-400'
      : 'text-amber-400'
    pills.push({ label: 'Caution', value: depositLabel, color: depositColor })
    if (status === 'returned_dispute') {
      pills.push({ label: 'Litige', value: 'En cours', color: 'text-red-400' })
    }
  } else if (status === 'completed') {
    pills.push({ label: 'Total encaissé', value: formatCents(reservation.paid_amount_cents ?? reservation.total_amount_cents), color: 'text-green-400' })
    const depositStatus = deposit?.status === 'retained' ? 'Retenue' : deposit?.status === 'released' ? 'Restituée' : depositHeld ? 'Encaissée' : 'N/A'
    const depositColor = deposit?.status === 'retained' ? 'text-amber-400' : 'text-green-400'
    pills.push({ label: 'Caution', value: depositStatus, color: depositColor })
  } else if (status === 'cancelled') {
    pills.push({ label: 'Statut', value: 'Annulée', color: 'text-dark-400' })
  }

  if (pills.length === 0) return null

  return (
    <div className="flex gap-2 flex-wrap pb-1 lg:flex-nowrap lg:overflow-x-auto">
      {pills.map((p, i) => (
        <div key={i} className="shrink-0 card px-4 py-2 min-w-[100px]">
          <div className="text-xs text-dark-500">{p.label}</div>
          <div className={cn('text-xs font-semibold mt-0.5', p.color || 'text-dark-200')}>{p.value}</div>
        </div>
      ))}
    </div>
  )
}
