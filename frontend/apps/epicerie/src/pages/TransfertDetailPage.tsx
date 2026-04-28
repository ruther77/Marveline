import { useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Clock, FileText, XCircle } from 'lucide-react'
import { useToast } from '@shared/components/ui/Toast'
import { epicerieApi } from '@/api/epicerie'
import TransferConfirmModal from '@/components/transferts/TransferConfirmModal'
import TransferSummary from '@/components/transferts/TransferSummary'
import type { TransferStatus } from '@/types/epicerie-v2'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents, formatDateTime } from '@/utils/etl-helpers'
import { getTransferDisplayHtCts, getTransferDisplayTtcCts } from '@/utils/transferts'

const STATUS: Record<TransferStatus, { label: string; cls: string; icon: typeof Clock }> = {
  PENDING: { label: 'En attente', cls: 'border-amber-200 bg-amber-50 text-amber-600', icon: Clock },
  VALIDATED: { label: 'Validé', cls: 'border-emerald-200 bg-emerald-50 text-emerald-600', icon: CheckCircle2 },
  CANCELLED: { label: 'Annulé', cls: 'border-slate-200 bg-slate-50 text-slate-500', icon: XCircle },
}

const INVOICE_STATUS_LABELS: Record<string, string> = {
  EN_ATTENTE: 'En attente',
  EN_RETARD: 'En retard',
  PAYEE: 'Payée',
}

function DetailSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-6 w-48 rounded bg-slate-100" />
      <div className="h-20 rounded-2xl bg-slate-100" />
      <div className="h-64 rounded-2xl bg-slate-100" />
    </div>
  )
}

export default function TransfertDetailPage() {
  const { id } = useParams({ from: '/_app/transferts/$id' })
  const qc = useQueryClient()
  const { success: toastOk, error: toastErr } = useToast()
  const transferId = Number(id)

  const [error, setError] = useState<string | null>(null)
  const [showValidateConfirm, setShowValidateConfirm] = useState(false)
  const [showCancelInput, setShowCancelInput] = useState(false)
  const [cancelReason, setCancelReason] = useState('')

  const { data: transfer, isLoading } = useQuery({
    queryKey: ['epicerie-transfert', transferId],
    queryFn: () => epicerieApi.getTransfert(transferId),
    enabled: transferId > 0,
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['epicerie-transfert', transferId] })
    qc.invalidateQueries({ queryKey: ['epicerie-transferts'] })
    qc.invalidateQueries({ queryKey: ['epicerie-stock-list'] })
    qc.invalidateQueries({ queryKey: ['epicerie-stock-stats'] })
  }

  const validateMut = useMutation({
    mutationFn: () => epicerieApi.validerTransfert(transferId),
    onSuccess: updated => {
      setError(null)
      setShowValidateConfirm(false)
      toastOk('Transfert validé', updated.reference || `TRF-${updated.id}`)
      invalidate()
    },
    onError: err => {
      const message = normalizeError(err).message || 'Erreur lors de la validation'
      setError(message)
      setShowValidateConfirm(false)
      toastErr('Erreur', message)
    },
  })

  const cancelMut = useMutation({
    mutationFn: () => epicerieApi.annulerTransfert(transferId, cancelReason.trim() || undefined),
    onSuccess: updated => {
      setError(null)
      setShowCancelInput(false)
      setCancelReason('')
      toastOk('Transfert annulé', updated.reference || `TRF-${updated.id}`)
      invalidate()
    },
    onError: err => {
      const message = normalizeError(err).message || 'Erreur lors de l’annulation'
      setError(message)
      toastErr('Erreur', message)
    },
  })

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl p-4 sm:p-6">
        <Link to="/transferts" className="text-sm text-slate-500 transition-colors hover:text-slate-700">
          ← Transferts
        </Link>
        <div className="mt-4">
          <DetailSkeleton />
        </div>
      </div>
    )
  }

  if (!transfer) {
    return (
      <div className="mx-auto max-w-3xl p-4 py-12 text-center sm:p-6">
        <p className="text-slate-400">Transfert introuvable.</p>
        <Link to="/transferts" className="mt-2 inline-block text-sm text-emerald-600 hover:underline">
          ← Retour
        </Link>
      </div>
    )
  }

  const cfg = STATUS[transfer.status]
  const Icon = cfg.icon
  const isPending = transfer.status === 'PENDING'
  const isValidated = transfer.status === 'VALIDATED'
  const totalHtCts = getTransferDisplayHtCts(transfer)
  const totalTtcCts = getTransferDisplayTtcCts(transfer)
  const invoiceStatusLabel = transfer.invoice_statut ? INVOICE_STATUS_LABELS[transfer.invoice_statut] || transfer.invoice_statut : null

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6">
      <Link to="/transferts" className="text-sm text-slate-500 transition-colors hover:text-slate-700">
        ← Transferts
      </Link>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">{transfer.reference || `Transfert #${transfer.id}`}</h1>
          <p className="mt-0.5 text-sm text-slate-500">{formatDateTime(transfer.created_at)}</p>
        </div>

        <span className={`inline-flex items-center gap-1.5 self-start rounded-lg border px-3 py-1.5 text-sm font-medium ${cfg.cls}`}>
          <Icon className="h-4 w-4" />
          {cfg.label}
        </span>
      </div>

      {isValidated && (
        <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />
          <div>
            <p className="text-sm font-medium text-emerald-800">Transfert validé</p>
            <p className="text-xs text-emerald-600">
              Stock épicerie décrémenté · Stock restaurant incrémenté
              {transfer.validated_at && ` · ${formatDateTime(transfer.validated_at)}`}
            </p>
          </div>
        </div>
      )}

      {transfer.status === 'CANCELLED' && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          Annulé
          {transfer.raison_annulation ? ` — ${transfer.raison_annulation}` : ''}
          {transfer.cancelled_at ? ` · ${formatDateTime(transfer.cancelled_at)}` : ''}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
          {error}
          <button type="button" onClick={() => setError(null)} className="ml-2 underline">
            fermer
          </button>
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
          <span className="text-sm font-semibold text-slate-700">
            Lignes ({transfer.lignes.length} article{transfer.lignes.length > 1 ? 's' : ''})
          </span>
        </div>

        <div className="divide-y divide-slate-100">
          {transfer.lignes.map(line => (
            <div key={line.id} className="flex items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-800">{line.designation}</p>
              </div>
              <span className="text-sm text-slate-500">
                {line.quantite} {line.unite}
              </span>
              <span className="text-xs text-slate-400">× {formatCents(line.prix_unitaire)}</span>
              <span className="w-24 text-right font-mono text-sm font-medium text-slate-700">
                {formatCents(line.montant_ht)}
              </span>
            </div>
          ))}
        </div>

        <TransferSummary
          totalHtCts={totalHtCts}
          totalTtcCts={totalTtcCts}
          totalTvaCts={totalTtcCts - totalHtCts}
        />
      </div>

      {transfer.notes && (
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
          <span className="font-medium text-slate-700">Notes:</span> {transfer.notes}
        </div>
      )}

      {transfer.invoice_id && (
        <a
          href={`/finance/invoices/${transfer.invoice_id}`}
          className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-slate-300 hover:bg-slate-50"
        >
          <FileText className="h-4 w-4 shrink-0 text-slate-400" />
          <div className="min-w-0 flex-1 text-sm text-slate-600">
            <span className="font-medium text-slate-700">
              {transfer.invoice_numero || `Facture interne #${transfer.invoice_id}`}
            </span>
            {invoiceStatusLabel && <span className="ml-2 text-emerald-600">{invoiceStatusLabel}</span>}
          </div>
          <span className="text-sm font-medium text-slate-500">Voir →</span>
        </a>
      )}

      {isPending ? (
        <div className="space-y-3 pt-2">
          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => setShowValidateConfirm(true)}
              className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-500"
            >
              <CheckCircle2 className="h-4 w-4" />
              Valider le transfert
            </button>

            {!showCancelInput ? (
              <button
                type="button"
                onClick={() => setShowCancelInput(true)}
                className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-600 transition-colors hover:bg-slate-50"
              >
                Annuler
              </button>
            ) : (
              <div className="flex flex-1 flex-col gap-2 sm:flex-row">
                <input
                  type="text"
                  value={cancelReason}
                  onChange={event => setCancelReason(event.target.value)}
                  placeholder="Raison (optionnel)"
                  className="min-h-11 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500/20"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => cancelMut.mutate()}
                    disabled={cancelMut.isPending}
                    className="inline-flex min-h-11 items-center justify-center rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500 disabled:opacity-50"
                  >
                    Confirmer
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowCancelInput(false)
                      setCancelReason('')
                    }}
                    className="inline-flex min-h-11 items-center justify-center rounded-lg px-3 py-2 text-sm text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                  >
                    ×
                  </button>
                </div>
              </div>
            )}
          </div>

          <p className="text-xs text-slate-400">
            La validation crée les mouvements de stock et la facture interne correspondante.
          </p>
        </div>
      ) : isValidated && transfer.validated_at ? (
        <p className="text-sm text-slate-500">Validé le {formatDateTime(transfer.validated_at)}</p>
      ) : null}

      {showValidateConfirm && (
        <TransferConfirmModal
          nbArticles={transfer.lignes.length}
          totalTtcCts={totalTtcCts}
          loading={validateMut.isPending}
          onConfirm={() => validateMut.mutate()}
          onCancel={() => {
            if (!validateMut.isPending) {
              setShowValidateConfirm(false)
            }
          }}
        />
      )}
    </div>
  )
}
