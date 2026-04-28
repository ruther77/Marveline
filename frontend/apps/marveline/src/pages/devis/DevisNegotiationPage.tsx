import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useParams, useNavigate } from '@tanstack/react-router'
import { ArrowLeft, Send, CheckCircle, XCircle } from 'lucide-react'
import { useDevisDetail, useAddNegotiationEntry, useConcludeNegotiation } from '@/api/queries/useDevis'
import { normalizeError } from '@shared/errors/normalizer'
import { ActionError } from '@shared/components/ui/ActionError'
import { formatDate, formatCents } from '@/lib/utils'
import { MoneyInput } from '@shared/components/ui/MoneyInput'

export default function DevisNegotiationPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const navigate = useNavigate()
  const devisId = parseInt(id, 10)

  const { data: devis, isLoading } = useDevisDetail(devisId)
  const addEntry = useAddNegotiationEntry()
  const conclude = useConcludeNegotiation()

  const [message, setMessage] = useState('')
  const [proposedCents, setProposedCents] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [showRefuse, setShowRefuse] = useState(false)
  const [refuseReason, setRefuseReason] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!message.trim()) return
    setError(null)

    const proposed_amount_cents = proposedCents > 0 ? proposedCents : undefined

    addEntry.mutate(
      { id: devisId, message: message.trim(), proposed_amount_cents },
      {
        onSuccess: () => {
          setMessage('')
          setProposedCents(0)
        },
        onError: (err) => {
          setError(
            normalizeError(err).message ||
              'Erreur lors de l\'envoi du message.'
          )
        },
      }
    )
  }

  if (isLoading) return (
    <div className="space-y-4 animate-pulse">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="card p-4 space-y-2">
          <div className="h-3 skel rounded w-36" />
          <div className="h-2 skel rounded w-52" />
        </div>
      ))}
    </div>
  )
  if (!devis) return <div className="p-6 text-center text-dark-400">Devis introuvable.</div>

  return (
    <div className="p-4 md:p-6 max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate({ to: '/devis/$id', params: { id: String(devisId) } })}
          className="p-2 hover:bg-dark-600 rounded text-dark-400"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <PageHeader title="Négociation" subtitle={`${devis.reference} · ${devis.customer_name}`} />
      </div>

      {/* Total actuel */}
      <div className="card flex items-center justify-between">
        <span className="text-dark-400 text-sm">Total actuel</span>
        <span className="text-gold-400 font-bold text-lg">{formatCents(devis.total_cents)}</span>
      </div>

      {/* Timeline */}
      <div className="space-y-4">
        {devis.negotiations.length === 0 ? (
          <p className="text-center text-dark-400 text-sm py-4">
            Aucun message de négociation pour ce devis.
          </p>
        ) : (
          devis.negotiations.map((entry) => (
            <div key={entry.id} className="card space-y-1">
              <div className="flex items-center justify-between text-xs text-dark-400">
                <span className="font-medium text-dark-300">{entry.author}</span>
                <span>{formatDate(entry.created_at)}</span>
              </div>
              <p className="text-sm">{entry.message}</p>
              {entry.proposed_amount_cents !== undefined && (
                <p className="text-gold-400 text-sm font-medium">
                  Proposition : {formatCents(entry.proposed_amount_cents)}
                </p>
              )}
            </div>
          ))
        )}
      </div>

      {/* Actions conclure */}
      {devis.status === 'negotiation' && (
        <div className="card space-y-3">
          <h3 className="font-medium text-sm">Conclure la negociation</h3>

          <ActionError
            message={conclude.error ? normalizeError(conclude.error).message || 'Erreur' : null}
            onDismiss={() => conclude.reset()}
          />

          <div className="flex gap-3">
            <button
              onClick={() => conclude.mutate(
                { id: devisId, outcome: 'accepted' },
                { onSuccess: () => navigate({ to: '/devis/$id', params: { id: String(devisId) } }) }
              )}
              disabled={conclude.isPending}
              className="flex-1 flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 text-white font-medium text-sm px-4 py-2.5 rounded-lg disabled:opacity-40 min-h-[44px]"
            >
              <CheckCircle className="w-4 h-4" />
              {conclude.isPending ? 'En cours...' : 'Accepter le devis'}
            </button>
            <button
              onClick={() => setShowRefuse(true)}
              disabled={conclude.isPending}
              className="flex-1 flex items-center justify-center gap-2 bg-red-600/10 hover:bg-red-600/20 text-red-400 font-medium text-sm px-4 py-2.5 rounded-lg border border-red-600/30 disabled:opacity-40 min-h-[44px]"
            >
              <XCircle className="w-4 h-4" />
              Refuser
            </button>
          </div>
        </div>
      )}

      {/* Modal refus */}
      {showRefuse && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={() => setShowRefuse(false)}>
          <div className="bg-dark-800 rounded-xl border border-dark-600 w-full max-w-md shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="px-5 py-4 border-b border-dark-600">
              <h2 className="font-bold">Refuser le devis</h2>
              <p className="text-dark-400 text-xs mt-1">{devis.reference} · {formatCents(devis.total_cents)}</p>
            </div>
            <div className="px-5 py-4 space-y-3">
              <label className="text-sm font-medium block">Raison du refus</label>
              <textarea
                rows={3}
                value={refuseReason}
                onChange={e => setRefuseReason(e.target.value)}
                placeholder="Indiquez la raison du refus..."
                className="input w-full"
              />
            </div>
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-dark-600">
              <button onClick={() => setShowRefuse(false)} className="text-sm text-dark-400 hover:text-dark-200 px-4 py-2">Annuler</button>
              <button
                onClick={() => conclude.mutate(
                  { id: devisId, outcome: 'refused', reason: refuseReason || undefined },
                  { onSuccess: () => { setShowRefuse(false); navigate({ to: '/devis/$id', params: { id: String(devisId) } }) } }
                )}
                disabled={conclude.isPending}
                className="bg-red-600 hover:bg-red-700 text-white font-medium text-sm px-4 py-2 rounded-lg disabled:opacity-40"
              >
                {conclude.isPending ? 'En cours...' : 'Confirmer le refus'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Hint statut draft : formulaire pas encore disponible */}
      {devis.status === 'draft' && (
        <p className="text-center text-dark-400 text-xs py-2">
          Le dialogue de négociation sera disponible une fois le devis envoyé au client.
        </p>
      )}

      {/* Formulaire */}
      {(devis.status === 'sent' || devis.status === 'negotiation') && (
        <form onSubmit={handleSubmit} className="card space-y-4">
          <h3 className="font-medium text-sm">Ajouter un message</h3>

          <textarea
            rows={3}
            placeholder="Votre message…"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="input"
          />

          <MoneyInput
            label="Montant proposé (€ HT) — optionnel"
            value={proposedCents}
            onChange={setProposedCents}
            placeholder="0,00"
          />

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={!message.trim() || addEntry.isPending}
              className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm px-6 py-2 rounded-lg disabled:opacity-40"
            >
              <Send className="w-4 h-4" />
              {addEntry.isPending ? 'Envoi…' : 'Envoyer'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
