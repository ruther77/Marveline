import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Check, X, AlertTriangle, RefreshCw, Inbox, Clock, Sparkles, CheckCircle,
} from 'lucide-react'
import { epicerieApi } from '@/api/epicerie'
import { Pagination } from '@/components/Pagination'
import { normalizeError } from '@shared/errors/normalizer'
import type {
  PreviewResolutionResponse,
  TransferRequestRead,
  TransferRequestStatus,
} from '@/types/epicerie-v2'

const DEMANDES_PER_PAGE = 20

const STATUS_FILTERS: { key: TransferRequestStatus | 'ALL'; label: string }[] = [
  { key: 'PENDING', label: 'En attente' },
  { key: 'APPROVED', label: 'Approuvées' },
  { key: 'REJECTED', label: 'Rejetées' },
  { key: 'CANCELLED', label: 'Annulées' },
  { key: 'ALL', label: 'Toutes' },
]

const STATUS_BADGE: Record<TransferRequestStatus, { cls: string; label: string }> = {
  PENDING:   { cls: 'bg-amber-50 text-amber-700 border border-amber-200',   label: 'En attente' },
  APPROVED:  { cls: 'bg-emerald-50 text-emerald-700 border border-emerald-200', label: 'Approuvée' },
  FULFILLED: { cls: 'bg-emerald-100 text-emerald-800 border border-emerald-300', label: 'Livrée' },
  REJECTED:  { cls: 'bg-red-50 text-red-700 border border-red-200',         label: 'Rejetée' },
  CANCELLED: { cls: 'bg-stone-100 text-stone-600 border border-stone-200',  label: 'Annulée' },
}

function fmtDateHeure(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

interface RejectDialogProps {
  requestId: number
  onClose: () => void
  onConfirm: (raison: string) => void
  isPending: boolean
}

function RejectDialog({ requestId, onClose, onConfirm, isPending }: RejectDialogProps) {
  const [raison, setRaison] = useState('')
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40">
      <div role="dialog" aria-modal="true" aria-labelledby={`reject-${requestId}`}
        className="bg-white border border-stone-200 w-full sm:max-w-md shadow-xl rounded-t-2xl sm:rounded-2xl pb-[env(safe-area-inset-bottom)] sm:pb-0">
        <div className="sm:hidden flex justify-center pt-2 pb-1">
          <div className="w-10 h-1 rounded-full bg-stone-300" />
        </div>
        <div className="px-5 py-4 border-b border-stone-200 flex items-center justify-between">
          <h3 id={`reject-${requestId}`} className="text-[16px] font-bold text-stone-900">
            Rejeter la demande
          </h3>
          <button onClick={onClose} aria-label="Fermer"
            className="text-stone-500 hover:text-stone-900 min-w-[44px] min-h-[44px] flex items-center justify-center -mr-2">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-5 py-4 flex flex-col gap-3">
          <label className="text-[12px] font-semibold text-stone-600 block">
            Raison du rejet (optionnel)
          </label>
          <textarea
            value={raison}
            onChange={e => setRaison(e.target.value)}
            placeholder="Ex: Stock épuisé, fournisseur en retard..."
            rows={3}
            maxLength={500}
            className="w-full bg-white border border-stone-200 rounded-xl px-3 py-2 text-[14px] focus:outline-none focus:border-amber-400 resize-none"
          />
        </div>
        <div className="flex gap-3 px-5 py-4 border-t border-stone-100">
          <button onClick={onClose}
            className="flex-1 h-12 text-[14px] text-stone-700 font-medium bg-stone-100 rounded-xl hover:bg-stone-200">
            Annuler
          </button>
          <button onClick={() => onConfirm(raison.trim())} disabled={isPending}
            className="flex-1 h-12 text-[14px] font-semibold text-white bg-red-600 rounded-xl hover:bg-red-700 disabled:opacity-50">
            {isPending ? 'Rejet…' : 'Rejeter'}
          </button>
        </div>
      </div>
    </div>
  )
}

interface PreviewResolutionBlockProps {
  requestId: number
  approvePending: boolean
  onApprove: () => void
  onClose: () => void
}

function PreviewResolutionBlock({ requestId, approvePending, onApprove, onClose }: PreviewResolutionBlockProps) {
  const { data, isLoading, error } = useQuery<PreviewResolutionResponse>({
    queryKey: ['transfer-request-preview', requestId],
    queryFn: () => epicerieApi.previewResolutionDemande(requestId),
  })

  if (isLoading) {
    return (
      <div className="px-5 py-3 border-t border-stone-100 bg-violet-50/60">
        <div className="text-[12px] text-violet-700 italic">
          Calcul de la proposition de transfert…
        </div>
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="px-5 py-3 border-t border-stone-100 bg-red-50">
        <div className="text-[12px] text-red-700">
          Erreur preview : {normalizeError(error).message}
        </div>
      </div>
    )
  }

  return (
    <div className="px-5 py-3 border-t border-stone-100 bg-violet-50/40">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 text-[12px] font-bold text-violet-800">
          <Sparkles className="h-3.5 w-3.5" />
          Proposition de transfert
        </div>
        <button
          onClick={onClose}
          aria-label="Masquer la proposition"
          className="text-violet-400 hover:text-violet-700 p-1"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {data.any_deficit && (
        <div className="flex items-start gap-1.5 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5 mb-2 text-[11px] text-amber-800">
          <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" />
          <span>
            Au moins un ingrédient est en couverture partielle. Le transfert
            sera créé avec le stock disponible, le reste restera à demander
            plus tard.
          </span>
        </div>
      )}

      {data.unresolvable_line_ids.length > 0 && (
        <div className="bg-stone-50 border border-stone-200 rounded-lg px-2.5 py-1.5 mb-2 text-[11px] text-stone-600">
          {data.unresolvable_line_ids.length} ligne(s) sans ingrédient mappé
          seront ignorées.
        </div>
      )}

      <div className="flex flex-col gap-2 mb-3">
        {data.lines.map((line) => (
          <div
            key={line.request_line_id}
            className={`border rounded-lg p-2.5 ${
              line.couverture_complete
                ? 'bg-emerald-50 border-emerald-200'
                : 'bg-amber-50 border-amber-200'
            }`}
          >
            <div className="flex items-center justify-between gap-2 mb-1">
              <div className="text-[12px] font-semibold text-stone-900 truncate">
                {line.ingredient_nom}
              </div>
              <div className="flex items-center gap-1 shrink-0 text-[11px] font-mono">
                {line.couverture_complete ? (
                  <>
                    <CheckCircle className="h-3 w-3 text-emerald-600" />
                    <span className="text-emerald-700">
                      {line.qte_besoin} couvert
                    </span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="h-3 w-3 text-amber-600" />
                    <span className="text-amber-700">
                      −{line.deficit} manquant
                    </span>
                  </>
                )}
              </div>
            </div>
            {line.items.length === 0 ? (
              <div className="text-[11px] text-stone-500 italic">
                Aucun produit épicerie disponible
              </div>
            ) : (
              <ul className="text-[11px] text-stone-700 space-y-0.5">
                {line.items.map((it) => (
                  <li
                    key={it.produit_id}
                    className="flex items-center justify-between gap-2"
                  >
                    <span className="truncate">
                      #{it.ordre + 1} {it.produit_designation}
                    </span>
                    <span className="font-mono text-stone-900 shrink-0">
                      {parseFloat(it.qte_prelevee_unites_vente).toFixed(2)}{' '}
                      {it.produit_unite_vente}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <button
          onClick={onClose}
          className="flex-1 h-10 text-[13px] text-stone-600 bg-white border border-stone-200 rounded-lg hover:bg-stone-50"
        >
          Annuler
        </button>
        <button
          onClick={onApprove}
          disabled={approvePending || data.lines.every((l) => l.items.length === 0)}
          className="flex-1 h-10 text-[13px] font-semibold text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center justify-center gap-1.5"
        >
          <Check className="h-3.5 w-3.5" />
          {approvePending ? 'Création…' : 'Créer le transfert'}
        </button>
      </div>
    </div>
  )
}

interface DemandeCardProps {
  demande: TransferRequestRead
}

function DemandeCard({ demande }: DemandeCardProps) {
  const qc = useQueryClient()
  const [showReject, setShowReject] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [error, setError] = useState('')
  const badge = STATUS_BADGE[demande.status]

  const approveMut = useMutation({
    mutationFn: () => epicerieApi.approuverDemande(demande.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['epicerie-transfer-requests'] })
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur approbation'),
  })

  const approveWithTransferMut = useMutation({
    mutationFn: () => epicerieApi.approveWithTransfer(demande.id, {}),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['epicerie-transfer-requests'] })
      qc.invalidateQueries({ queryKey: ['epicerie-internal-transfers'] })
      const warnCount = result.warnings.length
      setSuccessMsg(
        `Transfert #${result.transfer_id} créé`
        + (warnCount > 0 ? ` — ${warnCount} avertissement${warnCount > 1 ? 's' : ''}` : ''),
      )
      setShowPreview(false)
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur approbation + transfert'),
  })

  const rejectMut = useMutation({
    mutationFn: (raison: string) => epicerieApi.rejeterDemande(demande.id, raison),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['epicerie-transfer-requests'] })
      setShowReject(false)
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur rejet'),
  })

  const isPending = demande.status === 'PENDING'
  const hasResolvableLines = demande.lignes.some(l => l.ingredient_restaurant_id !== null)

  return (
    <>
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden shadow-sm">
        <div className="px-5 py-3 border-b border-stone-100 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="text-[14px] font-bold text-stone-900">
              Demande #{demande.id}
            </div>
            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${badge.cls}`}>
              {badge.label}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[12px] text-stone-500">
            <Clock className="h-3.5 w-3.5" />
            {fmtDateHeure(demande.created_at)}
          </div>
        </div>

        {demande.notes && (
          <div className="px-5 py-2 bg-amber-50/40 border-b border-stone-100 text-[13px] text-stone-700">
            <span className="font-semibold">Note :</span> {demande.notes}
          </div>
        )}

        <div className="px-5 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-stone-500 mb-2">
            {demande.lignes.length} produit{demande.lignes.length > 1 ? 's' : ''} demandé{demande.lignes.length > 1 ? 's' : ''}
          </div>
          <div className="flex flex-col gap-1.5">
            {demande.lignes.map(l => (
              <div key={l.id} className="flex items-center gap-3 px-3 py-2 bg-stone-50 rounded-lg">
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-medium text-stone-900">{l.designation}</div>
                  {l.notes && <div className="text-[12px] text-stone-500 italic mt-0.5">{l.notes}</div>}
                </div>
                <div className="text-[14px] font-bold text-stone-900 shrink-0">
                  {l.quantity} {l.unit}
                </div>
              </div>
            ))}
          </div>
        </div>

        {demande.rejection_reason && (
          <div className="px-5 py-2 bg-red-50/60 border-t border-red-100 text-[13px] text-red-700">
            <span className="font-semibold">Raison :</span> {demande.rejection_reason}
          </div>
        )}

        {successMsg && (
          <div className="px-5 py-2 bg-emerald-50 border-t border-emerald-200 flex items-center gap-2 text-[13px] text-emerald-700">
            <CheckCircle className="h-4 w-4 shrink-0" />
            <span className="flex-1">{successMsg}</span>
            <button onClick={() => setSuccessMsg(null)} aria-label="Fermer"
              className="text-emerald-600 min-h-[44px] min-w-[44px] flex items-center justify-center -mr-2">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {error && (
          <div className="px-5 py-2 bg-red-50 border-t border-red-200 flex items-center gap-2 text-[13px] text-red-700">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span className="flex-1">{error}</span>
            <button onClick={() => setError('')} aria-label="Fermer l'erreur"
              className="text-red-500 min-h-[44px] min-w-[44px] flex items-center justify-center -mr-2">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {isPending && showPreview && (
          <PreviewResolutionBlock
            requestId={demande.id}
            approvePending={approveWithTransferMut.isPending}
            onApprove={() => approveWithTransferMut.mutate()}
            onClose={() => setShowPreview(false)}
          />
        )}

        {isPending && (
          <div className="flex flex-col sm:flex-row gap-2 px-5 py-3 border-t border-stone-100 bg-stone-50">
            {hasResolvableLines && !showPreview && (
              <button
                onClick={() => setShowPreview(true)}
                disabled={approveMut.isPending || approveWithTransferMut.isPending || rejectMut.isPending}
                className="flex-1 h-12 flex items-center justify-center gap-2 text-[14px] font-semibold text-violet-700 bg-violet-50 border border-violet-200 rounded-xl hover:bg-violet-100 disabled:opacity-50"
              >
                <Sparkles className="h-4 w-4" />
                Voir la proposition
              </button>
            )}
            <button
              onClick={() => setShowReject(true)}
              disabled={approveMut.isPending || approveWithTransferMut.isPending || rejectMut.isPending}
              className="flex-1 h-12 flex items-center justify-center gap-2 text-[14px] font-semibold text-red-700 bg-white border border-red-200 rounded-xl hover:bg-red-50 disabled:opacity-50"
            >
              <X className="h-4 w-4" />
              Rejeter
            </button>
            {!hasResolvableLines && (
              <button
                onClick={() => approveMut.mutate()}
                disabled={approveMut.isPending || approveWithTransferMut.isPending || rejectMut.isPending}
                className="flex-1 h-12 flex items-center justify-center gap-2 text-[14px] font-semibold text-white bg-emerald-600 rounded-xl hover:bg-emerald-700 disabled:opacity-50"
              >
                <Check className="h-4 w-4" />
                {approveMut.isPending ? 'Approbation…' : 'Approuver (sans transfert)'}
              </button>
            )}
          </div>
        )}
      </div>

      {showReject && (
        <RejectDialog
          requestId={demande.id}
          onClose={() => setShowReject(false)}
          onConfirm={(raison) => rejectMut.mutate(raison)}
          isPending={rejectMut.isPending}
        />
      )}
    </>
  )
}

export default function TransfertDemandesPage() {
  const [filter, setFilter] = useState<TransferRequestStatus | 'ALL'>('PENDING')
  const [page, setPage] = useState(1)

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['epicerie-transfer-requests', filter, page],
    queryFn: () => epicerieApi.listTransferRequests({
      status: filter === 'ALL' ? undefined : filter,
      page,
      per_page: DEMANDES_PER_PAGE,
    }),
    staleTime: 15_000,
    refetchInterval: 30_000,
    placeholderData: prev => prev,
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0

  function handleFilterChange(next: TransferRequestStatus | 'ALL') {
    setFilter(next)
    setPage(1)
  }

  return (
    <div className="flex flex-col min-h-0 h-full bg-stone-50">
      {/* Header */}
      <div className="bg-white border-b border-stone-200 px-4 sm:px-6 py-4 flex items-center gap-3 flex-wrap">
        <h1 className="text-[18px] font-bold text-stone-900 tracking-tight">Demandes restaurant</h1>
        <span className="text-[12px] text-stone-500">{total} résultat{total > 1 ? 's' : ''}</span>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="ml-auto flex items-center gap-1.5 h-10 px-3 text-[12px] font-medium text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-lg disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          Actualiser
        </button>
      </div>

      {/* Filtres */}
      <div className="bg-white border-b border-stone-100 px-4 sm:px-6 py-2.5 flex items-center gap-2 overflow-x-auto">
        {STATUS_FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => handleFilterChange(f.key)}
            className={`shrink-0 h-10 px-4 text-[13px] font-medium rounded-full transition-colors min-w-[44px] ${
              filter === f.key
                ? 'bg-stone-900 text-white'
                : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-4">
        {isLoading ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="animate-pulse bg-stone-200 rounded-2xl h-40" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <div className="w-14 h-14 rounded-2xl bg-stone-100 flex items-center justify-center">
              <Inbox className="h-6 w-6 text-stone-400" />
            </div>
            <p className="text-[14px] font-semibold text-stone-700">Aucune demande</p>
            <p className="text-[12px] text-stone-500 max-w-xs">
              {filter === 'PENDING'
                ? 'Aucune demande en attente. Le restaurant n\'a rien demandé pour l\'instant.'
                : `Aucune demande dans le statut « ${STATUS_FILTERS.find(s => s.key === filter)?.label} ».`}
            </p>
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-3">
              {items.map(d => <DemandeCard key={d.id} demande={d} />)}
            </div>
            <div className="mt-4">
              <Pagination
                page={page}
                total={total}
                perPage={DEMANDES_PER_PAGE}
                onPageChange={setPage}
                itemLabel="demande"
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
