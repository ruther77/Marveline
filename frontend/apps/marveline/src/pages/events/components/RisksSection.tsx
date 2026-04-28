import { useState } from 'react'
import { AlertTriangle, Trash2 } from 'lucide-react'
import { useReservationRisks, useCreateRisk, useDeleteRisk } from '@/api/queries'
import { ActionError } from '@shared/components/ui/ActionError'
import { normalizeError } from '@shared/errors/normalizer'
import { cn } from '@/lib/utils'
import type { ReservationDetail, ReservationRiskCreate } from '@/types/reservation'

interface Props {
  reservation: ReservationDetail
}

export function RisksSection({ reservation }: Props) {
  const { data: risks = [] } = useReservationRisks(reservation.id)
  const createRiskMutation = useCreateRisk()
  const deleteRiskMutation = useDeleteRisk()

  const [showRiskForm, setShowRiskForm] = useState(false)
  const [riskType, setRiskType] = useState('')
  const [riskSeverity, setRiskSeverity] = useState<'low' | 'medium' | 'high'>('low')
  const [riskDescription, setRiskDescription] = useState('')

  if (reservation.status === 'cancelled' || reservation.status === 'completed') return null

  return (
    <div className="border-t border-dark-600 pt-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-medium flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-orange-400" />
          Risques ({risks.length})
        </h3>
        {!showRiskForm && (
          <button onClick={() => setShowRiskForm(true)} className="btn-secondary btn-sm">
            + Signaler
          </button>
        )}
      </div>

      {showRiskForm && (
        <div className="space-y-2 p-4 card">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-dark-400">Type</label>
              <input
                type="text"
                value={riskType}
                onChange={(e) => setRiskType(e.target.value)}
                placeholder="ex: annulation, retard..."
                className="input-dark w-full text-sm mt-1"
              />
            </div>
            <div>
              <label className="text-xs text-dark-400">Sévérité</label>
              <select
                value={riskSeverity}
                onChange={(e) => setRiskSeverity(e.target.value as 'low' | 'medium' | 'high')}
                className="input-dark w-full text-sm mt-1"
              >
                <option value="low">Faible</option>
                <option value="medium">Moyen</option>
                <option value="high">Élevé</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-dark-400">Description</label>
            <textarea
              value={riskDescription}
              onChange={(e) => setRiskDescription(e.target.value)}
              rows={2}
              placeholder="Décrivez le risque..."
              className="input-dark w-full text-sm mt-1 resize-none"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => {
                const data: ReservationRiskCreate = {
                  type: riskType,
                  severity: riskSeverity,
                  description: riskDescription,
                }
                createRiskMutation.mutate({ reservationId: reservation.id, data }, {
                  onSuccess: () => {
                    setShowRiskForm(false)
                    setRiskType('')
                    setRiskDescription('')
                    setRiskSeverity('low')
                  },
                })
              }}
              disabled={createRiskMutation.isPending || !riskType || !riskDescription}
              className="btn-primary btn-sm"
            >
              {createRiskMutation.isPending ? 'Ajout...' : 'Ajouter'}
            </button>
            <button onClick={() => setShowRiskForm(false)} className="btn-secondary btn-sm">Annuler</button>
          </div>
          <ActionError
            message={createRiskMutation.error ? normalizeError(createRiskMutation.error).message || 'Erreur ajout risque' : null}
            onDismiss={() => createRiskMutation.reset()}
          />
        </div>
      )}

      {risks.length > 0 && (
        <div className="space-y-2">
          {risks.map((risk) => (
            <div key={risk.id} className={cn(
              'flex items-start gap-4 p-4 rounded-lg border',
              risk.severity === 'high' ? 'bg-red-900/10 border-red-700/30' :
              risk.severity === 'medium' ? 'bg-orange-900/10 border-orange-700/30' :
              'bg-dark-900 border-dark-600',
              risk.resolved_at ? 'opacity-50' : '',
            )}>
              <AlertTriangle className={cn(
                'w-4 h-4 shrink-0 mt-0.5',
                risk.severity === 'high' ? 'text-red-400' :
                risk.severity === 'medium' ? 'text-orange-400' : 'text-yellow-400',
              )} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-dark-200">{risk.type}</span>
                  {risk.resolved_at && (
                    <span className="text-xs px-1.5 py-0.5 bg-green-900/30 text-green-400 rounded">Résolu</span>
                  )}
                </div>
                <p className="text-xs text-dark-400 mt-0.5">{risk.description}</p>
              </div>
              {!risk.resolved_at && (
                <button
                  onClick={() => deleteRiskMutation.mutate({ reservationId: reservation.id, riskId: risk.id })}
                  disabled={deleteRiskMutation.isPending}
                  className="shrink-0 text-dark-500 hover:text-red-400"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
