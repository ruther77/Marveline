import { useState } from 'react'
import { CalendarPlus } from 'lucide-react'
import { useExtendReservation } from '@/api/queries'
import { ActionError } from '@shared/components/ui/ActionError'
import { normalizeError } from '@shared/errors/normalizer'
import type { ReservationDetail } from '@/types/reservation'

interface Props {
  reservation: ReservationDetail
}

export function ExtendSection({ reservation }: Props) {
  const extendMutation = useExtendReservation()

  const [showExtendForm, setShowExtendForm] = useState(false)
  const [extendDate, setExtendDate] = useState('')
  const [extendReason, setExtendReason] = useState('')
  const [extendExtraEuros, setExtendExtraEuros] = useState('')

  if (reservation.status !== 'delivered' && reservation.status !== 'extended') return null

  return (
    <div className="border-t border-dark-600 pt-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-medium flex items-center gap-2">
          <CalendarPlus className="w-4 h-4" />
          Prolonger la réservation
        </h3>
        {!showExtendForm && (
          <button onClick={() => setShowExtendForm(true)} className="btn-secondary btn-sm">
            Prolonger
          </button>
        )}
      </div>

      {showExtendForm && (
        <div className="space-y-2 p-4 card">
          <div>
            <label className="text-xs text-dark-400">Nouvelle date de retour</label>
            <input
              type="date"
              value={extendDate}
              onChange={(e) => setExtendDate(e.target.value)}
              min={reservation.return_date}
              className="input-dark w-full text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-dark-400">Motif</label>
            <input
              type="text"
              value={extendReason}
              onChange={(e) => setExtendReason(e.target.value)}
              placeholder="Raison de la prolongation..."
              className="input-dark w-full text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-dark-400">Supplément (EUR, optionnel)</label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={extendExtraEuros}
              onChange={(e) => setExtendExtraEuros(e.target.value)}
              placeholder="0.00"
              className="input-dark w-full text-sm mt-1"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => extendMutation.mutate({
                reservationId: reservation.id,
                data: {
                  new_return_date: extendDate,
                  reason: extendReason,
                  extra_charge_cents: extendExtraEuros
                    ? Math.round(parseFloat(extendExtraEuros) * 100)
                    : undefined,
                },
              }, {
                onSuccess: () => {
                  setShowExtendForm(false)
                  setExtendDate('')
                  setExtendReason('')
                  setExtendExtraEuros('')
                },
              })}
              disabled={extendMutation.isPending || !extendDate || !extendReason}
              className="btn-primary btn-sm"
            >
              {extendMutation.isPending ? 'Enregistrement...' : 'Confirmer prolongation'}
            </button>
            <button onClick={() => setShowExtendForm(false)} className="btn-secondary btn-sm">
              Annuler
            </button>
          </div>
          <ActionError
            message={extendMutation.error ? normalizeError(extendMutation.error).message || 'Erreur prolongation' : null}
            onDismiss={() => extendMutation.reset()}
          />
        </div>
      )}
    </div>
  )
}
