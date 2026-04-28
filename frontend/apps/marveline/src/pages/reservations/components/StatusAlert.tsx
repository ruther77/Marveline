import { Check, Truck, Info, AlertTriangle, XCircle } from 'lucide-react'
import { formatDate } from '@/lib/utils'
import type { ReservationDetail } from '@/types/reservation'
import type { Deposit } from '@/types/deposit'

interface StatusAlertProps {
  reservation: Pick<ReservationDetail, 'status' | 'return_date' | 'deposit_paid'>
  deposit?: Deposit
  customMessage?: string
}

export function StatusAlert({ reservation, deposit, customMessage }: StatusAlertProps) {
  const { status } = reservation

  if (customMessage) {
    return (
      <div className="flex gap-2 p-4 rounded-lg bg-dark-900/60 border border-dark-600 text-sm text-dark-300">
        <Info className="w-4 h-4 text-dark-400 shrink-0 mt-0.5" />
        {customMessage}
      </div>
    )
  }

  if (status === 'draft') return (
    <div className="flex gap-2 p-4 rounded-lg bg-dark-900/60 border border-dark-600 text-sm text-dark-300">
      <Info className="w-4 h-4 text-dark-400 shrink-0 mt-0.5" />
      Complète les produits manquants puis confirme pour réserver le stock.
    </div>
  )

  if (status === 'confirmed_risk') return (
    <div className="flex gap-2 p-4 rounded-lg bg-red-900/20 border border-red-700/30 text-sm text-red-300">
      <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
      Caution + acompte en retard. Sans règlement, la sortie matériel doit être suspendue.
    </div>
  )

  if (status === 'confirmed') return (
    <div className="flex gap-2 p-4 rounded-lg bg-amber-900/20 border border-amber-700/30 text-sm text-amber-300">
      <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
      Le départ matériel reste bloqué tant que caution et acompte ne sont pas validés.
    </div>
  )

  if (status === 'pre_check') {
    const depositOk = reservation.deposit_paid || deposit?.status === 'held'
    if (!depositOk) {
      return (
        <div className="flex gap-2 p-4 rounded-lg bg-amber-900/20 border border-amber-700/30 text-sm text-amber-300">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          Pre-check valide mais caution en attente. Le depart est bloque.
        </div>
      )
    }
    return (
      <div className="flex gap-2 p-4 rounded-lg bg-green-900/20 border border-green-700/30 text-sm text-green-300">
        <Check className="w-4 h-4 text-green-400 shrink-0 mt-0.5" />
        Caution et acompte valides. Le depart peut etre lance.
      </div>
    )
  }

  if (status === 'delivered' || status === 'extended') return (
    <div className="flex gap-2 p-4 rounded-lg bg-blue-900/20 border border-blue-700/30 text-sm text-blue-300">
      <Truck className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
      Matériel sorti. Retour prévu le {formatDate(reservation.return_date)}.
    </div>
  )

  if (status === 'returned') {
    const depositStatus = deposit?.status
    // Caution déjà traitée (restituée ou retenue) → plus rien à faire sur la caution
    if (depositStatus === 'released' || depositStatus === 'retained') {
      return (
        <div className="flex gap-2 p-4 rounded-lg bg-green-900/20 border border-green-700/30 text-sm text-green-300">
          <Check className="w-4 h-4 text-green-400 shrink-0 mt-0.5" />
          Retour et caution traités. Clôture pour archiver la réservation.
        </div>
      )
    }
    return (
      <div className="flex gap-2 p-4 rounded-lg bg-orange-900/20 border border-orange-700/30 text-sm text-orange-300">
        <Info className="w-4 h-4 text-orange-400 shrink-0 mt-0.5" />
        Retour enregistré. Restitue la caution puis clôture pour finaliser.
      </div>
    )
  }

  if (status === 'returned_dispute') return (
    <div className="flex gap-2 p-4 rounded-lg bg-orange-900/20 border border-orange-700/30 text-sm text-orange-300">
      <AlertTriangle className="w-4 h-4 text-orange-400 shrink-0 mt-0.5" />
      Litige en cours — arbitrage en attente.
    </div>
  )

  if (status === 'completed') return (
    <div className="flex gap-2 p-4 rounded-lg bg-purple-900/20 border border-purple-700/30 text-sm text-purple-300">
      <Check className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
      Réservation clôturée. Caution restituée.
    </div>
  )

  if (status === 'cancelled') return (
    <div className="flex gap-2 p-4 rounded-lg bg-dark-900/60 border border-dark-600 text-sm text-dark-400">
      <XCircle className="w-4 h-4 text-dark-500 shrink-0 mt-0.5" />
      Réservation annulée.
    </div>
  )

  return null
}
