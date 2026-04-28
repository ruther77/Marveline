import { useState } from 'react'
import {
  AlertTriangle,
  MessageSquarePlus,
  Coins,
  CheckCircle2,
  Loader2,
} from 'lucide-react'
import { Button } from '@shared/components/ui'
import { normalizeError } from '@shared/errors/normalizer'
import { useDisputeLogs, useAddDisputeLog } from '@/api/queries'
import { useToast } from '@/hooks'
import type { DisputeLog, DisputeAction } from '@/types/reservation'

interface DisputeLogTimelineProps {
  reservationId: number
}

const actionConfig: Record<
  DisputeAction,
  { icon: typeof AlertTriangle; label: string; tone: string }
> = {
  opened: { icon: AlertTriangle, label: 'Litige ouvert', tone: 'text-amber-400' },
  note_added: {
    icon: MessageSquarePlus,
    label: 'Note ajoutée',
    tone: 'text-dark-300',
  },
  charge_applied: {
    icon: Coins,
    label: 'Charge imputée',
    tone: 'text-primary-400',
  },
  resolved: {
    icon: CheckCircle2,
    label: 'Litige résolu',
    tone: 'text-emerald-400',
  },
}

function LogEntry({ log }: { log: DisputeLog }) {
  const cfg = actionConfig[log.action]
  const Icon = cfg.icon
  const dt = new Date(log.created_at)
  return (
    <li className="flex gap-3 pb-3 last:pb-0">
      <div className="flex flex-col items-center">
        <Icon className={`w-4 h-4 mt-0.5 ${cfg.tone}`} />
        <div className="w-px flex-1 bg-dark-700 mt-1" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-2">
          <span className={`text-sm font-medium ${cfg.tone}`}>{cfg.label}</span>
          <time className="text-xs text-dark-500 shrink-0">
            {dt.toLocaleString('fr-FR', {
              day: '2-digit',
              month: 'short',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </time>
        </div>
        <p className="text-sm text-dark-200 mt-0.5 break-words">{log.description}</p>
        {log.charge_cents > 0 && (
          <p className="text-xs text-dark-400 mt-0.5">
            Montant : <strong>{(log.charge_cents / 100).toFixed(2)} €</strong>
          </p>
        )}
      </div>
    </li>
  )
}

/**
 * Timeline append-only des entrées d'un litige + formulaire d'ajout de note.
 *
 * - Affiche la chronologie par created_at asc (backend renvoie déjà trié).
 * - Permet d'ajouter une `note_added` ou `charge_applied`.
 * - La résolution (`resolved`) passe par l'endpoint /close-dispute (autre bouton).
 */
export function DisputeLogTimeline({ reservationId }: DisputeLogTimelineProps) {
  const toast = useToast()
  const { data, isLoading } = useDisputeLogs(reservationId)
  const mut = useAddDisputeLog()

  const [draftAction, setDraftAction] = useState<DisputeAction>('note_added')
  const [draftDesc, setDraftDesc] = useState('')
  const [draftCharge, setDraftCharge] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  const canSubmit = draftDesc.trim().length >= 3 && !mut.isPending

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const charge =
      draftAction === 'charge_applied' && draftCharge
        ? Math.round(parseFloat(draftCharge) * 100)
        : 0

    mut.mutate(
      {
        reservationId,
        payload: {
          action: draftAction,
          description: draftDesc.trim(),
          charge_cents: charge,
        },
      },
      {
        onSuccess: () => {
          toast.success('Entrée ajoutée', 'Le journal du litige a été mis à jour.')
          setDraftDesc('')
          setDraftCharge('')
        },
        onError: (err) => {
          setError(normalizeError(err).message || 'Erreur lors de l\'ajout')
        },
      },
    )
  }

  if (isLoading) {
    return (
      <div className="card">
        <div className="space-y-2">
          <div className="h-4 w-32 bg-dark-700 rounded animate-pulse" />
          <div className="h-3 w-full bg-dark-700 rounded animate-pulse" />
          <div className="h-3 w-3/4 bg-dark-700 rounded animate-pulse" />
        </div>
      </div>
    )
  }

  const logs = data ?? []

  return (
    <section className="card space-y-4">
      <header className="flex items-center gap-2">
        <AlertTriangle className="w-5 h-5 text-amber-400" />
        <h3 className="font-semibold">Journal du litige</h3>
        <span className="text-xs text-dark-400 ml-auto">
          {logs.length} entrée{logs.length > 1 ? 's' : ''}
        </span>
      </header>

      {logs.length === 0 ? (
        <p className="text-sm text-dark-400">
          Aucune entrée pour l'instant. Ajoutez une note pour démarrer le journal.
        </p>
      ) : (
        <ol className="space-y-0">
          {logs.map((log) => (
            <LogEntry key={log.id} log={log} />
          ))}
        </ol>
      )}

      <form onSubmit={handleSubmit} className="space-y-2 border-t border-dark-700 pt-3">
        <div className="flex gap-2">
          <select
            value={draftAction}
            onChange={(e) => setDraftAction(e.target.value as DisputeAction)}
            className="input"
          >
            <option value="note_added">Note</option>
            <option value="charge_applied">Charge imputée</option>
          </select>
          {draftAction === 'charge_applied' && (
            <input
              type="number"
              step="0.01"
              min="0"
              value={draftCharge}
              onChange={(e) => setDraftCharge(e.target.value)}
              placeholder="Montant €"
              className="input w-32"
            />
          )}
        </div>
        <textarea
          rows={2}
          value={draftDesc}
          onChange={(e) => setDraftDesc(e.target.value)}
          placeholder="Décrire l'événement…"
          className="input w-full text-sm"
          minLength={3}
          maxLength={500}
          required
        />
        {error && (
          <p className="text-xs text-red-300 bg-red-900/30 border border-red-600/40 rounded px-2 py-1">
            {error}
          </p>
        )}
        <div className="flex justify-end">
          <Button
            type="submit"
            variant="primary"
            disabled={!canSubmit}
            onClick={handleSubmit as unknown as () => void}
          >
            {mut.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin mr-1" /> Ajout…
              </>
            ) : (
              'Ajouter au journal'
            )}
          </Button>
        </div>
      </form>
    </section>
  )
}
