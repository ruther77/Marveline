import { PageHeader } from '@/components/PageHeader'
import { useParams } from '@tanstack/react-router'
import { useState } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents, cn } from '@/lib/utils'
import { ArrowLeft, FileX } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { EmptyState } from '@shared/components/ui/EmptyState'
import { ActionError } from '@shared/components/ui/ActionError'
import { useInvoiceDetail, useInvoiceCreditNotes, useCreateCreditNote, useApplyCreditNote, useRefundCreditNote } from '@/api/queries'
import { useHasScope } from '@/hooks/useHasScope'
import type { CreditNote } from '@/types/invoice'

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  draft:    { label: 'Brouillon', color: 'text-dark-400',   bg: 'bg-dark-900 border-dark-600' },
  issued:   { label: 'Émis',      color: 'text-blue-400',   bg: 'bg-blue-500/10 border-blue-500/30' },
  applied:  { label: 'Imputé',    color: 'text-green-400',  bg: 'bg-green-500/10 border-green-500/30' },
  refunded: { label: 'Remboursé', color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/30' },
}

interface CreateCreditNoteFormProps {
  invoiceId: number
  onSuccess: () => void
  onCancel: () => void
  canCreate: boolean
}

function CreateCreditNoteForm({ invoiceId, onSuccess, onCancel, canCreate }: CreateCreditNoteFormProps) {
  const mutation = useCreateCreditNote(invoiceId)
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate(
      { amount_cents: Math.round(parseFloat(amount) * 100), reason, issue_date: date },
      { onSuccess },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="card p-4 mt-4 space-y-4">
      <h3 className="text-sm font-semibold">Nouvel avoir</h3>
      <ActionError
        message={mutation.error ? normalizeError(mutation.error).message || "Erreur lors de la création de l'avoir" : null}
        onDismiss={() => mutation.reset()}
      />
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-dark-400 mb-1">Montant (€)</label>
          <input
            type="number"
            min={0.01}
            step={0.01}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full card px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            required
          />
        </div>
        <div>
          <label className="block text-xs text-dark-400 mb-1">Date</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full card px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            required
          />
        </div>
      </div>
      <div>
        <label className="block text-xs text-dark-400 mb-1">Motif</label>
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Annulation prestation, erreur facturation…"
          className="w-full card px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          required
        />
      </div>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm rounded-lg border border-dark-600 hover:bg-dark-600 transition-colors"
        >
          Annuler
        </button>
        <button
          type="submit"
          disabled={mutation.isPending || !canCreate}
          className="px-4 py-2 text-sm rounded-lg bg-primary-500 text-white hover:bg-primary-500/90 transition-colors disabled:opacity-50"
        >
          {mutation.isPending ? 'Création…' : "Créer l'avoir"}
        </button>
      </div>
    </form>
  )
}

interface CreditNoteCardProps {
  note: CreditNote
  canWrite?: boolean
  onApply?: () => void
  onRefund?: () => void
  isApplying?: boolean
  isRefunding?: boolean
}

function CreditNoteCard({
  note,
  canWrite = false,
  onApply,
  onRefund,
  isApplying = false,
  isRefunding = false,
}: CreditNoteCardProps) {
  const cfg = STATUS_CONFIG[note.status] ?? STATUS_CONFIG.issued
  const busy = isApplying || isRefunding
  return (
    <div className="card p-0 overflow-hidden">
      {/* Hero */}
      <div className="bg-purple-900/20 border-b border-purple-500/20 px-4 py-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-purple-300">{note.invoice_number}</p>
          <p className="text-xs text-purple-400/60 mt-0.5">
            Émis le {new Date(note.issue_date).toLocaleDateString('fr-FR')}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xl font-bold text-purple-300">−{formatCents(note.amount_cents)}</p>
          <span className={cn('text-xs px-2 py-0.5 rounded-full border font-medium', cfg.bg, cfg.color)}>
            {cfg.label}
          </span>
        </div>
      </div>
      {/* Body */}
      <div className="px-4 py-4 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-dark-400">Motif</span>
          <span className="font-medium max-w-xs text-right">{note.reason}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-dark-400">Montant</span>
          <span className="font-semibold">−{formatCents(note.amount_cents)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-dark-400">Statut</span>
          <span className={cfg.color}>{cfg.label}</span>
        </div>
        {note.status === 'issued' && canWrite && (
          <div className="flex gap-2 pt-2 border-t border-dark-600">
            <button
              type="button"
              onClick={onRefund}
              disabled={busy}
              className="flex-1 text-xs px-4 py-2 rounded-lg bg-green-500/10 text-green-400 border border-green-500/30 hover:bg-green-500/20 transition-colors disabled:opacity-50"
            >
              {isRefunding ? 'Remboursement…' : 'Rembourser maintenant'}
            </button>
            <button
              type="button"
              onClick={onApply}
              disabled={busy}
              className="flex-1 text-xs px-4 py-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/30 hover:bg-blue-500/20 transition-colors disabled:opacity-50"
            >
              {isApplying ? 'Imputation…' : 'Imputer sur prochaine facture'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export function AvoirsPage() {
  const canWrite = useHasScope('invoices:write')
  const { id } = useParams({ strict: false }) as { id: string }
  const invoiceId = isNaN(Number(id)) ? null : Number(id)
  const [showForm, setShowForm] = useState(false)

  const { data: invoiceDetail, isLoading: loadingInvoice } = useInvoiceDetail(invoiceId)
  const { data: creditNotes = [], isLoading: loadingNotes } = useInvoiceCreditNotes(invoiceId)
  const applyMutation = useApplyCreditNote(invoiceId ?? 0)
  const refundMutation = useRefundCreditNote(invoiceId ?? 0)

  const isLoading = loadingInvoice || loadingNotes
  const totalAvoirs = creditNotes.reduce((s, n) => s + n.amount_cents, 0)
  const actionError = applyMutation.error || refundMutation.error

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <Link
          to="/finance/invoices"
          className="p-2 rounded-lg hover:bg-dark-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 text-dark-400" />
        </Link>
        <div className="flex-1">
          <PageHeader title="Avoirs & Notes de crédit" subtitle={invoiceDetail ? `Facture ${invoiceDetail.invoice_number}${invoiceDetail.customer_name ? ` · ${invoiceDetail.customer_name}` : ''}` : undefined} />
        </div>
        {canWrite && (
          <button
            onClick={() => setShowForm((v) => !v)}
            className="px-4 py-1.5 text-sm rounded-lg bg-primary-500 text-white hover:bg-primary-500/90 transition-colors"
          >
            {showForm ? 'Annuler' : '+ Avoir'}
          </button>
        )}
      </div>

      {/* Formulaire création */}
      {showForm && canWrite && (
        <CreateCreditNoteForm
          invoiceId={invoiceId!}
          onSuccess={() => setShowForm(false)}
          onCancel={() => setShowForm(false)}
          canCreate={canWrite}
        />
      )}

      {/* Info facture source */}
      {invoiceDetail && (
        <div className="card p-4 mb-6 flex items-center justify-between">
          <div>
            <p className="text-xs text-dark-400">Facture source</p>
            <p className="text-sm font-semibold mt-0.5">{invoiceDetail.invoice_number}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-dark-400">Total facture</p>
            <p className="text-sm font-semibold">{formatCents(invoiceDetail.total_amount_cents)}</p>
          </div>
          {totalAvoirs > 0 && (
            <div className="text-right">
              <p className="text-xs text-dark-400">Total avoirs</p>
              <p className="text-sm font-semibold text-purple-400">−{formatCents(totalAvoirs)}</p>
            </div>
          )}
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="space-y-4">
          {[...Array(2)].map((_, i) => <div key={i} className="h-32 bg-dark-900 rounded-xl animate-pulse" />)}
        </div>
      )}

      {/* Empty */}
      {!isLoading && creditNotes.length === 0 && (
        <EmptyState
          icon={<FileX className="w-8 h-8" />}
          title="Aucun avoir"
          description="Aucune note de crédit n'a été émise pour cette facture."
        />
      )}

      {/* Erreur action avoir */}
      {actionError != null && (
        <ActionError
          message={normalizeError(actionError).message || "Erreur lors de la mise à jour de l'avoir"}
          onDismiss={() => { applyMutation.reset(); refundMutation.reset() }}
        />
      )}

      {/* Credit notes */}
      {!isLoading && creditNotes.length > 0 && (
        <div className="space-y-4">
          {creditNotes.map((note) => (
            <CreditNoteCard
              key={note.id}
              note={note}
              canWrite={canWrite}
              onApply={() => applyMutation.mutate(note.id)}
              onRefund={() => refundMutation.mutate(note.id)}
              isApplying={applyMutation.isPending && applyMutation.variables === note.id}
              isRefunding={refundMutation.isPending && refundMutation.variables === note.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}
