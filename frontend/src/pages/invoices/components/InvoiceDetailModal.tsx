import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { invoicesApi } from '@/api/invoices'
import { Modal } from '@/components/ui/Modal'
import { formatDate } from '@/lib/utils'
import { cn } from '@/lib/utils'
import {
  Calendar,
  CreditCard,
  FileText,
  Banknote,
  XCircle,
} from 'lucide-react'
import type { InvoiceStatus, PaymentMethod } from '@/types/invoice'

interface InvoiceDetailModalProps {
  isOpen: boolean
  onClose: () => void
  invoiceId?: number
}

const STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: 'Brouillon',
  sent: 'Envoyee',
  paid: 'Payee',
  overdue: 'En retard',
  cancelled: 'Annulee',
}

const STATUS_COLORS: Record<InvoiceStatus, string> = {
  draft: 'bg-dark-700 text-dark-300',
  sent: 'bg-blue-500/10 text-blue-500',
  paid: 'bg-green-500/10 text-green-500',
  overdue: 'bg-red-500/10 text-red-500',
  cancelled: 'bg-dark-700 text-dark-400',
}

const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  cash: 'Especes',
  card: 'Carte bancaire',
  transfer: 'Virement',
  check: 'Cheque',
}

function formatEuros(cents: number): string {
  return (cents / 100).toFixed(2) + ' EUR'
}

export function InvoiceDetailModal({ isOpen, onClose, invoiceId }: InvoiceDetailModalProps) {
  const queryClient = useQueryClient()
  const [showPaymentForm, setShowPaymentForm] = useState(false)
  const [paymentAmount, setPaymentAmount] = useState('')
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('card')
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0])

  const { data: invoice, isLoading } = useQuery({
    queryKey: ['invoice', invoiceId],
    queryFn: () => invoicesApi.getInvoice(invoiceId!),
    enabled: isOpen && !!invoiceId,
  })

  const paymentMutation = useMutation({
    mutationFn: ({ id, amount_cents, method, date }: {
      id: number
      amount_cents: number
      method: PaymentMethod
      date: string
    }) => invoicesApi.addPayment(id, {
      amount_cents,
      payment_method: method,
      payment_date: date,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', invoiceId] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      setShowPaymentForm(false)
      setPaymentAmount('')
    },
  })

  const cancelMutation = useMutation({
    mutationFn: (id: number) => invoicesApi.cancelInvoice(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', invoiceId] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
  })

  const handleSubmitPayment = () => {
    if (!invoice || !paymentAmount) return
    const cents = Math.round(parseFloat(paymentAmount) * 100)
    if (cents <= 0 || cents > invoice.remaining_amount_cents) return
    paymentMutation.mutate({
      id: invoice.id,
      amount_cents: cents,
      method: paymentMethod,
      date: paymentDate,
    })
  }

  const handleClose = () => {
    setShowPaymentForm(false)
    setPaymentAmount('')
    onClose()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Details de la facture"
      size="lg"
    >
      {isLoading ? (
        <div className="text-center py-8 text-dark-400">Chargement...</div>
      ) : invoice ? (
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileText className="w-5 h-5 text-primary-400" />
              <span className="font-mono text-lg text-primary-400">
                {invoice.invoice_number}
              </span>
              <span
                className={cn(
                  'inline-flex items-center px-2 py-1 rounded text-xs',
                  STATUS_COLORS[invoice.status]
                )}
              >
                {STATUS_LABELS[invoice.status]}
              </span>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              {!invoice.is_paid && invoice.status !== 'cancelled' && (
                <>
                  <button
                    onClick={() => setShowPaymentForm(!showPaymentForm)}
                    className="btn-primary btn-sm flex items-center gap-1"
                  >
                    <CreditCard className="w-3 h-3" />
                    Paiement
                  </button>
                  <button
                    onClick={() => cancelMutation.mutate(invoice.id)}
                    disabled={cancelMutation.isPending}
                    className="btn-secondary btn-sm flex items-center gap-1 text-red-400"
                  >
                    <XCircle className="w-3 h-3" />
                    Annuler
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Payment progress bar */}
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-dark-400">Progression paiement</span>
              <span className="font-medium">
                {invoice.payment_completion_percentage.toFixed(0)}%
              </span>
            </div>
            <div className="w-full bg-dark-700 rounded-full h-2">
              <div
                className={cn(
                  'h-2 rounded-full transition-all',
                  invoice.is_paid ? 'bg-green-500' :
                  invoice.payment_completion_percentage > 0 ? 'bg-primary-500' :
                  'bg-dark-600'
                )}
                style={{ width: `${Math.min(100, invoice.payment_completion_percentage)}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-dark-500 mt-1">
              <span>Paye: {formatEuros(invoice.paid_amount_cents)}</span>
              <span>Restant: {formatEuros(invoice.remaining_amount_cents)}</span>
            </div>
          </div>

          {/* Payment form */}
          {showPaymentForm && (
            <div className="p-4 bg-dark-800 border border-dark-700 rounded-lg space-y-3">
              <h4 className="font-medium flex items-center gap-2">
                <Banknote className="w-4 h-4" />
                Enregistrer un paiement
              </h4>

              {paymentMutation.error && (
                <div className="p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
                  {(paymentMutation.error as Error).message || 'Erreur lors du paiement'}
                </div>
              )}

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Montant (EUR) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    max={(invoice.remaining_amount_cents / 100).toFixed(2)}
                    value={paymentAmount}
                    onChange={(e) => setPaymentAmount(e.target.value)}
                    placeholder={(invoice.remaining_amount_cents / 100).toFixed(2)}
                    className="input w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Methode *</label>
                  <select
                    value={paymentMethod}
                    onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
                    className="input w-full"
                  >
                    {Object.entries(PAYMENT_METHOD_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-dark-400 mb-1">Date *</label>
                  <input
                    type="date"
                    value={paymentDate}
                    onChange={(e) => setPaymentDate(e.target.value)}
                    className="input w-full"
                  />
                </div>
              </div>

              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => {
                    setShowPaymentForm(false)
                    setPaymentAmount('')
                  }}
                  className="btn-secondary btn-sm"
                >
                  Annuler
                </button>
                <button
                  onClick={handleSubmitPayment}
                  disabled={paymentMutation.isPending || !paymentAmount}
                  className="btn-primary btn-sm"
                >
                  {paymentMutation.isPending ? 'Envoi...' : 'Valider le paiement'}
                </button>
              </div>
            </div>
          )}

          {/* Info grid */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-dark-400">Date d'emission</label>
              <div className="flex items-center gap-2 mt-1">
                <Calendar className="w-4 h-4 text-dark-400" />
                <span>{formatDate(invoice.issue_date)}</span>
              </div>
            </div>

            <div>
              <label className="text-sm text-dark-400">Date d'echeance</label>
              <div className="flex items-center gap-2 mt-1">
                <Calendar className={cn(
                  'w-4 h-4',
                  invoice.is_overdue ? 'text-red-400' : 'text-dark-400'
                )} />
                <span className={invoice.is_overdue ? 'text-red-400 font-medium' : ''}>
                  {formatDate(invoice.due_date)}
                </span>
              </div>
            </div>

            <div>
              <label className="text-sm text-dark-400">Montant total</label>
              <p className="font-medium mt-1 text-lg">
                {formatEuros(invoice.total_amount_cents)}
              </p>
            </div>

            <div>
              <label className="text-sm text-dark-400">Montant paye</label>
              <p className={cn(
                'font-medium mt-1 text-lg',
                invoice.is_paid ? 'text-green-400' : ''
              )}>
                {formatEuros(invoice.paid_amount_cents)}
              </p>
            </div>

            {invoice.payment_method && (
              <div>
                <label className="text-sm text-dark-400">Methode de paiement</label>
                <div className="flex items-center gap-2 mt-1">
                  <CreditCard className="w-4 h-4 text-dark-400" />
                  <span>{PAYMENT_METHOD_LABELS[invoice.payment_method]}</span>
                </div>
              </div>
            )}

            {invoice.payment_date && (
              <div>
                <label className="text-sm text-dark-400">Date de paiement</label>
                <div className="flex items-center gap-2 mt-1">
                  <Calendar className="w-4 h-4 text-green-400" />
                  <span>{formatDate(invoice.payment_date)}</span>
                </div>
              </div>
            )}
          </div>

          {/* Linked reservation */}
          {invoice.reservation && (
            <div className="border-t border-dark-700 pt-4">
              <label className="text-sm text-dark-400">Reservation liee</label>
              <div className="mt-2 p-3 bg-dark-800 rounded-lg border border-dark-700">
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-mono text-sm text-primary-400">
                      {invoice.reservation.reference}
                    </span>
                    {invoice.reservation.customer_name && (
                      <span className="text-sm text-dark-300 ml-3">
                        {invoice.reservation.customer_name}
                      </span>
                    )}
                  </div>
                  <span className="text-sm text-dark-400">
                    {formatDate(invoice.reservation.event_date)}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Timestamps */}
          <div className="border-t border-dark-700 pt-4 flex gap-6 text-xs text-dark-500">
            <span>Cree le {formatDate(invoice.created_at)}</span>
            <span>Modifie le {formatDate(invoice.updated_at)}</span>
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-dark-400">Facture introuvable</div>
      )}
    </Modal>
  )
}
