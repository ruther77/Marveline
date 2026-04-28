import { useState } from 'react'
import { Check, Banknote, Bell } from 'lucide-react'
import { useCreateDeposit, useUpdateDeposit, useRemindReservationDeposit } from '@/api/queries'
import { ActionError } from '@shared/components/ui/ActionError'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents, cn } from '@/lib/utils'
import { DEPOSIT_STATUS_LABELS, DEPOSIT_STATUS_COLORS } from '@/lib/constants'
import type { ReservationDetail } from '@/types/reservation'
import type { Deposit } from '@/types/deposit'

const REMIND_DEPOSIT_STATUSES = ['confirmed', 'pre_check', 'confirmed_risk'] as const
type RemindDepositStatus = typeof REMIND_DEPOSIT_STATUSES[number]

interface Props {
  reservation: ReservationDetail
  reservationId: number
  currentDeposit?: Deposit
}

export function DepositSection({ reservation, reservationId, currentDeposit }: Props) {
  const createDepositMutation = useCreateDeposit()
  const updateDepositMutation = useUpdateDeposit()
  const remindDepositMutation = useRemindReservationDeposit()

  const canRemind = (
    !currentDeposit &&
    reservation.deposit_amount_cents > 0 &&
    REMIND_DEPOSIT_STATUSES.includes(reservation.status as RemindDepositStatus)
  )

  const [showDepositForm, setShowDepositForm] = useState(false)
  const [depositAmountEuros, setDepositAmountEuros] = useState('')
  const [depositNotes, setDepositNotes] = useState('')
  const [showRetainForm, setShowRetainForm] = useState(false)
  const [retainAmountEuros, setRetainAmountEuros] = useState('')
  const [retainNotes, setRetainNotes] = useState('')

  return (
    <div className="space-y-4">
      {currentDeposit ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <span className="text-dark-300">{formatCents(currentDeposit.amount_cents)}</span>
            <span className={cn('text-xs px-2 py-0.5 rounded', DEPOSIT_STATUS_COLORS[currentDeposit.status])}>
              {DEPOSIT_STATUS_LABELS[currentDeposit.status]}
            </span>
          </div>

          {currentDeposit.status === 'held' && !showRetainForm && (
            <div className="flex gap-2">
              <button
                onClick={() => updateDepositMutation.mutate({
                  reservationId,
                  depositId: currentDeposit.id,
                  data: { status: 'released', release_date: new Date().toISOString().split('T')[0] },
                })}
                disabled={updateDepositMutation.isPending}
                className="btn-secondary btn-sm flex items-center gap-1 text-green-400"
              >
                <Check className="w-3 h-3" /> Restituer
              </button>
              <button onClick={() => setShowRetainForm(true)} className="btn-secondary btn-sm text-orange-400">
                Retenir (partiel)
              </button>
            </div>
          )}

          {showRetainForm && (
            <div className="space-y-2 p-4 card">
              <p className="text-sm text-dark-300">Montant retenu (EUR)</p>
              <input type="number" step="0.01" min="0" value={retainAmountEuros}
                onChange={(e) => setRetainAmountEuros(e.target.value)} placeholder="ex: 50.00"
                className="input-dark w-full text-sm" />
              <input type="text" value={retainNotes}
                onChange={(e) => setRetainNotes(e.target.value)} placeholder="Motif (optionnel)"
                className="input-dark w-full text-sm" />
              <div className="flex gap-2">
                <button
                  onClick={() => updateDepositMutation.mutate({
                    reservationId,
                    depositId: currentDeposit.id,
                    data: {
                      status: 'retained',
                      retained_amount_cents: Math.round(parseFloat(retainAmountEuros || '0') * 100),
                      notes: retainNotes || undefined,
                    },
                  }, {
                    onSuccess: () => { setShowRetainForm(false); setRetainAmountEuros(''); setRetainNotes('') },
                  })}
                  disabled={updateDepositMutation.isPending || !retainAmountEuros}
                  className="btn-primary btn-sm"
                >
                  {updateDepositMutation.isPending ? 'Enregistrement...' : 'Confirmer'}
                </button>
                <button onClick={() => setShowRetainForm(false)} className="btn-secondary btn-sm">Annuler</button>
              </div>
            </div>
          )}

          <ActionError
            message={updateDepositMutation.error ? normalizeError(updateDepositMutation.error).message || 'Erreur mise à jour caution' : null}
            onDismiss={() => updateDepositMutation.reset()}
          />
        </div>
      ) : (
        <div className="space-y-2">
          {reservation.deposit_amount_cents > 0 && (
            <button
              onClick={() => createDepositMutation.mutate({
                reservationId,
                data: {
                  amount_cents: reservation.deposit_amount_cents,
                  collection_date: new Date().toISOString().split('T')[0],
                },
              })}
              disabled={createDepositMutation.isPending}
              className="btn-secondary btn-sm flex items-center gap-1 text-green-400"
            >
              <Check className="w-3 h-3" />
              {createDepositMutation.isPending ? 'Enregistrement...' : `Encaisser caution (${formatCents(reservation.deposit_amount_cents)})`}
            </button>
          )}

          {canRemind && (
            <>
              <button
                onClick={() => remindDepositMutation.mutate(reservationId)}
                disabled={remindDepositMutation.isPending || remindDepositMutation.isSuccess}
                className="btn-secondary btn-sm flex items-center gap-1 text-amber-400"
              >
                <Bell className="w-3 h-3" />
                {remindDepositMutation.isPending
                  ? 'Envoi...'
                  : remindDepositMutation.isSuccess
                    ? 'Relance envoyée'
                    : 'Relancer le client'}
              </button>
              <ActionError
                message={remindDepositMutation.error ? normalizeError(remindDepositMutation.error).message || 'Erreur envoi relance' : null}
                onDismiss={() => remindDepositMutation.reset()}
              />
            </>
          )}
          {!showDepositForm ? (
            <button onClick={() => setShowDepositForm(true)} className="btn-secondary btn-sm flex items-center gap-1">
              <Banknote className="w-3 h-3" /> Enregistrer caution
            </button>
          ) : (
            <div className="space-y-2 p-4 card">
              <p className="text-sm text-dark-300">Montant (EUR)</p>
              <input type="number" step="0.01" min="0" value={depositAmountEuros}
                onChange={(e) => setDepositAmountEuros(e.target.value)} placeholder="ex: 200.00"
                className="input-dark w-full text-sm" />
              <input type="text" value={depositNotes}
                onChange={(e) => setDepositNotes(e.target.value)} placeholder="Notes (optionnel)"
                className="input-dark w-full text-sm" />
              <div className="flex gap-2">
                <button
                  onClick={() => createDepositMutation.mutate({
                    reservationId,
                    data: {
                      amount_cents: Math.round(parseFloat(depositAmountEuros || '0') * 100),
                      notes: depositNotes || undefined,
                    },
                  }, {
                    onSuccess: () => { setShowDepositForm(false); setDepositAmountEuros(''); setDepositNotes('') },
                  })}
                  disabled={createDepositMutation.isPending || !depositAmountEuros}
                  className="btn-primary btn-sm"
                >
                  {createDepositMutation.isPending ? 'Enregistrement...' : 'Enregistrer'}
                </button>
                <button onClick={() => setShowDepositForm(false)} className="btn-secondary btn-sm">Annuler</button>
              </div>
              <ActionError
                message={createDepositMutation.error ? normalizeError(createDepositMutation.error).message || 'Erreur création caution' : null}
                onDismiss={() => createDepositMutation.reset()}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
