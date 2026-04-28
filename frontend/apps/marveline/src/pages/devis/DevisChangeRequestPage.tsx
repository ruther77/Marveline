import { useState } from 'react'
import { useParams } from '@tanstack/react-router'
import { GitPullRequest, CheckCircle2, XCircle, Clock } from 'lucide-react'
import {
  useDevisChangeRequests,
  useDevisMutations,
  useRequestChange,
  useUpdateDevisChangeRequest,
} from '@/api/queries/useDevis'
import { normalizeError } from '@shared/errors/normalizer'
import { ActionError } from '@shared/components/ui'
import type { DevisChangeRequest } from '@/types/devis'

type CRStatus = 'pending' | 'accepted' | 'refused'

const STATUS_LABELS: Record<CRStatus, string> = {
  pending: 'En attente',
  accepted: 'Acceptée',
  refused: 'Refusée',
}

const STATUS_COLORS: Record<CRStatus, string> = {
  pending: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  accepted: 'bg-green-500/15 text-green-400 border-green-500/30',
  refused: 'bg-red-500/15 text-red-400 border-red-500/30',
}

const STATUS_ICON: Record<CRStatus, React.ReactNode> = {
  pending: <Clock className="w-4 h-4 text-yellow-400" />,
  accepted: <CheckCircle2 className="w-4 h-4 text-green-400" />,
  refused: <XCircle className="w-4 h-4 text-red-400" />,
}

export default function DevisChangeRequestPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const devisId = parseInt(id, 10)

  const { data: changeRequests = [], isLoading } = useDevisChangeRequests(devisId)
  const requestChange = useRequestChange()
  const updateCR = useUpdateDevisChangeRequest()
  const { markVersionPending } = useDevisMutations()

  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [description, setDescription] = useState('')
  const [updatingId, setUpdatingId] = useState<number | null>(null)
  const [activeFilter, setActiveFilter] = useState<CRStatus | 'all'>('all')

  const errHandler = (err: unknown) =>
    setError(
      normalizeError(err).message ||
        'Une erreur est survenue.'
    )

  const total = changeRequests.length
  const pending = changeRequests.filter((cr) => cr.status === 'pending').length
  const accepted = changeRequests.filter((cr) => cr.status === 'accepted').length
  const refused = changeRequests.filter((cr) => cr.status === 'refused').length

  const handleSubmit = () => {
    if (!description.trim()) return
    setError(null)
    requestChange.mutate(
      { id: devisId, description: description.trim() },
      {
        onSuccess: () => {
          setDescription('')
          setShowForm(false)
        },
        onError: errHandler,
      }
    )
  }

  const handleUpdateStatus = async (cr: DevisChangeRequest, status: CRStatus) => {
    setError(null)
    setUpdatingId(cr.id)
    try {
      await updateCR.mutateAsync({ devisId, crId: cr.id, status })
      if (status === 'accepted') {
        await markVersionPending.mutateAsync(devisId)
      }
      setUpdatingId(null)
    } catch (err) {
      setUpdatingId(null)
      errHandler(err)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="card p-4 flex gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex-1 h-10 skel rounded" />
          ))}
        </div>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card p-4 h-20 skel/40 rounded" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Hero stats */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <GitPullRequest className="w-4 h-4 text-primary-400" />
            <span className="text-sm font-medium">Demandes de modification</span>
          </div>
          <button
            onClick={() => setShowForm(true)}
            className="text-xs px-4 py-1.5 bg-primary-500/10 text-primary-400 border border-primary-500/30 rounded-lg hover:bg-primary-500/20"
          >
            + Nouvelle demande
          </button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-dark-900 rounded-lg p-4 text-center">
            <div className="text-xl font-bold">{total}</div>
            <div className="text-xs text-dark-400 mt-0.5">Total</div>
          </div>
          <div className="bg-dark-900 rounded-lg p-4 text-center">
            <div className="text-xl font-bold text-yellow-400">{pending}</div>
            <div className="text-xs text-dark-400 mt-0.5">En attente</div>
          </div>
          <div className="bg-dark-900 rounded-lg p-4 text-center">
            <div className="text-xl font-bold text-green-400">{accepted}</div>
            <div className="text-xs text-dark-400 mt-0.5">Acceptées</div>
          </div>
          <div className="bg-dark-900 rounded-lg p-4 text-center">
            <div className="text-xl font-bold text-red-400">{refused}</div>
            <div className="text-xs text-dark-400 mt-0.5">Refusées</div>
          </div>
        </div>
      </div>

      <ActionError message={error} onDismiss={() => setError(null)} />

      {/* Filtres pills */}
      {changeRequests.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {(['all', 'pending', 'accepted', 'refused'] as (CRStatus | 'all')[]).map((f) => {
            const count = f === 'all' ? changeRequests.length : changeRequests.filter((cr) => cr.status === f).length
            const label = f === 'all' ? 'Tout' : STATUS_LABELS[f as CRStatus]
            const activeColor = f === 'all'
              ? 'bg-primary-500/15 text-primary-400 border-primary-500/30'
              : STATUS_COLORS[f as CRStatus]
            return (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                className={`px-4 py-1.5 text-xs rounded-full border font-medium transition-colors ${
                  activeFilter === f ? activeColor : 'border-dark-600 text-dark-400 hover:border-dark-500'
                }`}
              >
                {label} <span className="opacity-70">({count})</span>
              </button>
            )
          })}
        </div>
      )}

      {/* Formulaire nouvelle demande */}
      {showForm && (
        <div className="card p-4 space-y-4 border border-primary-500/20">
          <p className="text-sm font-medium">Nouvelle demande de modification</p>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Décrivez la modification souhaitée..."
            rows={3}
            className="w-full card px-4 py-2 text-sm focus:outline-none focus:border-primary-500 resize-none"
            autoFocus
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => { setShowForm(false); setDescription('') }}
              className="px-4 py-1.5 text-sm text-dark-400 hover:text-dark-50"
            >
              Annuler
            </button>
            <button
              onClick={handleSubmit}
              disabled={!description.trim() || requestChange.isPending}
              className="px-4 py-1.5 text-sm bg-primary-500 text-white rounded-lg disabled:opacity-50"
            >
              Soumettre
            </button>
          </div>
        </div>
      )}

      {/* Liste CRs */}
      {(() => {
        const filteredCRs = activeFilter === 'all' ? changeRequests : changeRequests.filter((cr) => cr.status === activeFilter)
        if (filteredCRs.length === 0 && !showForm) {
          return (
            <div className="text-center text-dark-400 text-sm py-10">
              {changeRequests.length === 0
                ? <><span>Aucune demande de modification.</span><br /><span className="text-xs mt-1 block">Soumettez une demande pour démarrer le dialogue.</span></>
                : <span>Aucune demande pour ce filtre.</span>
              }
            </div>
          )
        }
        return (
        <div className="space-y-4">
          {filteredCRs.map((cr) => {
            const status = cr.status as CRStatus
            const isUpdating = updatingId === cr.id
            return (
              <div key={cr.id} className="card p-4 space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-2 min-w-0">
                    <span className="mt-0.5 shrink-0">{STATUS_ICON[status]}</span>
                    <p className="text-sm">{cr.description}</p>
                  </div>
                  <span className={`text-xs px-2.5 py-1 rounded-full border font-medium shrink-0 ${STATUS_COLORS[status]}`}>
                    {STATUS_LABELS[status]}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs text-dark-500">
                    {new Date(cr.created_at).toLocaleDateString('fr-FR')}
                  </span>
                  {status === 'pending' && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleUpdateStatus(cr, 'refused')}
                        disabled={isUpdating}
                        className="text-xs px-2.5 py-1 border border-red-500/30 text-red-400 rounded-lg hover:bg-red-500/10 disabled:opacity-50"
                      >
                        Refuser
                      </button>
                      <button
                        onClick={() => handleUpdateStatus(cr, 'accepted')}
                        disabled={isUpdating}
                        className="text-xs px-2.5 py-1 border border-green-500/30 text-green-400 rounded-lg hover:bg-green-500/10 disabled:opacity-50"
                      >
                        Accepter
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
        )
      })()}
    </div>
  )
}
