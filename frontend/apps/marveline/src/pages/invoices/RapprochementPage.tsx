import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { ArrowLeftRight, AlertCircle, Clock } from 'lucide-react'
import { useAddPaymentRecord, useInvoicesList } from '@/api/queries/useInvoices'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents } from '@/lib/utils'
import { DomainStatusBadge } from '@shared/components/ui/DomainStatusBadge'
import { EmptyState } from '@shared/components/ui/EmptyState'
import type { InvoiceListItem } from '@/types/invoice'
import type { PaymentCreate } from '@/types/payment'

function daysUntilDue(dueDateStr: string): number {
  const due = new Date(dueDateStr)
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  return Math.ceil((due.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

interface PaymentFormState {
  amount_cents: number
  payment_method: PaymentCreate['payment_method']
  payment_date: string
  notes: string
}

interface InlinePaymentFormProps {
  invoice: InvoiceListItem
  onSuccess: () => void
  onCancel: () => void
}

function InlinePaymentForm({ invoice, onSuccess, onCancel }: InlinePaymentFormProps) {
  const remaining = invoice.total_amount_cents - invoice.paid_amount_cents
  const paymentMutation = useAddPaymentRecord()
  const [form, setForm] = useState<PaymentFormState>({
    amount_cents: remaining,
    payment_method: 'transfer',
    payment_date: today(),
    notes: '',
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await paymentMutation.mutateAsync({
        invoiceId: invoice.id,
        data: {
          amount_cents: form.amount_cents,
          payment_method: form.payment_method,
          payment_date: form.payment_date,
          notes: form.notes || undefined,
        },
      })
      onSuccess()
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur lors de l\'enregistrement du paiement')
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="card p-4 mt-2 space-y-4"
    >
      {error && (
        <p className="text-sm text-red-500 flex items-center gap-1">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </p>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="col-span-1">
          <label className="block text-xs text-dark-400 mb-1">Montant (€)</label>
          <input
            type="number"
            min={1}
            step={0.01}
            value={(form.amount_cents / 100).toFixed(2)}
            onChange={(e) =>
              setForm((f) => ({ ...f, amount_cents: Math.round(parseFloat(e.target.value) * 100) }))
            }
            className="w-full card px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            required
          />
        </div>

        <div className="col-span-1">
          <label className="block text-xs text-dark-400 mb-1">Méthode</label>
          <select
            value={form.payment_method}
            onChange={(e) =>
              setForm((f) => ({ ...f, payment_method: e.target.value as PaymentCreate['payment_method'] }))
            }
            className="w-full card px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="transfer">Virement</option>
            <option value="cash">Espèces</option>
            <option value="card">Carte</option>
            <option value="check">Chèque</option>
          </select>
        </div>

        <div className="col-span-1">
          <label className="block text-xs text-dark-400 mb-1">Date</label>
          <input
            type="date"
            value={form.payment_date}
            onChange={(e) => setForm((f) => ({ ...f, payment_date: e.target.value }))}
            className="w-full card px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            required
          />
        </div>

        <div className="col-span-1">
          <label className="block text-xs text-dark-400 mb-1">Note (optionnel)</label>
          <input
            type="text"
            value={form.notes}
            onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
            placeholder="Référence…"
            className="w-full card px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
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
          disabled={paymentMutation.isPending}
          className="px-4 py-2 text-sm rounded-lg bg-primary-500 text-white hover:bg-primary-500/90 transition-colors disabled:opacity-50"
        >
          {paymentMutation.isPending ? 'Enregistrement…' : 'Confirmer le paiement'}
        </button>
      </div>
    </form>
  )
}

export function RapprochementPage() {
  const [openPaymentId, setOpenPaymentId] = useState<number | null>(null)

  const {
    data: sentData,
    isLoading: loadingSent,
    error: sentError,
    refetch: refetchSent,
  } = useInvoicesList({ status: 'sent', limit: 200 })

  const {
    data: overdueData,
    isLoading: loadingOverdue,
    error: overdueError,
    refetch: refetchOverdue,
  } = useInvoicesList({ status: 'overdue', limit: 200 })

  const isLoading = loadingSent || loadingOverdue
  const queryError = sentError || overdueError
  const refetchAll = () => { refetchSent(); refetchOverdue() }

  const invoices: InvoiceListItem[] = (() => {
    const all = [
      ...(sentData?.items ?? []),
      ...(overdueData?.items ?? []),
    ]
    const seen = new Set<number>()
    return all
      .filter((inv) => {
        if (seen.has(inv.id)) return false
        seen.add(inv.id)
        return inv.status !== 'cancelled' && inv.status !== 'paid'
      })
      .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime())
  })()

  const handlePaymentSuccess = () => {
    setOpenPaymentId(null)
  }

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-4">
        <div className="flex items-center gap-2 mb-6">
          <ArrowLeftRight className="w-5 h-5 text-primary-400" />
          <PageHeader title="Rapprochement factures" />
        </div>
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="card p-4 flex items-center gap-4">
              <div className="flex-1 space-y-2">
                <div className="flex items-center gap-3">
                  <div className="h-4 bg-dark-800 rounded w-24" />
                  <div className="h-5 w-16 bg-dark-800 rounded-full" />
                </div>
                <div className="h-3 bg-dark-800 rounded w-44" />
              </div>
              <div className="h-5 bg-dark-800 rounded w-20" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (queryError) {
    return (
      <div className="card text-center py-12">
        <p className="text-red-400 mb-4">Erreur lors du chargement du rapprochement.</p>
        <button onClick={() => refetchAll()} className="btn-secondary text-sm">Réessayer</button>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center gap-2 mb-6">
        <ArrowLeftRight className="w-5 h-5 text-primary-400" />
        <h1 className="text-xl font-bold">Rapprochement factures</h1>
        {invoices.length > 0 && (
          <span className="ml-auto text-sm text-dark-400">
            {invoices.length} facture{invoices.length > 1 ? 's' : ''} en attente
          </span>
        )}
      </div>

      {invoices.length === 0 ? (
        <EmptyState
          icon={<ArrowLeftRight className="w-8 h-8" />}
          title="Aucune facture en attente"
          description="Toutes vos factures sont réglées."
        />
      ) : (
        <div className="space-y-2">
          {invoices.map((inv) => {
            const remaining = inv.total_amount_cents - inv.paid_amount_cents
            const days = daysUntilDue(inv.due_date)
            const isOpen = openPaymentId === inv.id

            return (
              <div
                key={inv.id}
                className="card p-0 overflow-hidden"
              >
                <div className="flex items-center gap-4 px-4 py-4">
                  {/* Statut urgence */}
                  <div className="shrink-0">
                    {inv.is_overdue ? (
                      <AlertCircle className="w-4 h-4 text-red-500" />
                    ) : days <= 7 ? (
                      <Clock className="w-4 h-4 text-orange-400" />
                    ) : null}
                  </div>

                  {/* Numéro + client */}
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold truncate">
                      {inv.invoice_number}
                      {inv.customer_name && (
                        <span className="font-normal text-dark-400 ml-2">{inv.customer_name}</span>
                      )}
                    </p>
                    <p className="text-xs text-dark-400">
                      Échéance :{' '}
                      <span
                        className={
                          inv.is_overdue
                            ? 'text-red-500 font-medium'
                            : days <= 7
                            ? 'text-orange-400 font-medium'
                            : ''
                        }
                      >
                        {new Date(inv.due_date).toLocaleDateString('fr-FR')}
                        {inv.is_overdue && ' (en retard)'}
                        {!inv.is_overdue && days <= 7 && ` (dans ${days}j)`}
                      </span>
                    </p>
                  </div>

                  {/* Montants */}
                  <div className="text-right shrink-0 hidden sm:block">
                    <p className="text-sm text-dark-400">Total : {formatCents(inv.total_amount_cents)}</p>
                    <p className="text-sm font-semibold">
                      Reste : {formatCents(remaining)}
                    </p>
                  </div>

                  {/* Statut */}
                  <div className="shrink-0">
                    <DomainStatusBadge status={inv.status} />
                  </div>

                  {/* Action */}
                  <button
                    onClick={() => setOpenPaymentId(isOpen ? null : inv.id)}
                    className={`shrink-0 px-4 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                      isOpen
                        ? 'bg-dark-900 text-dark-400 border border-dark-600'
                        : 'bg-primary-500 text-white hover:bg-primary-500/90'
                    }`}
                  >
                    {isOpen ? 'Annuler' : 'Payer'}
                  </button>
                </div>

                {/* Montant mobile */}
                <div className="sm:hidden px-4 pb-2 flex gap-4 text-xs text-dark-400">
                  <span>Total : {formatCents(inv.total_amount_cents)}</span>
                  <span className="font-medium">Reste : {formatCents(remaining)}</span>
                </div>

                {isOpen && (
                  <div className="px-4 pb-4">
                    <InlinePaymentForm
                      invoice={inv}
                      onSuccess={handlePaymentSuccess}
                      onCancel={() => setOpenPaymentId(null)}
                    />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
