import { useState } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { Banknote, Check } from 'lucide-react'
import { PAYMENT_METHOD_LABELS } from '@/lib/constants'
import type { PaymentMethod } from '@/types/invoice'

const PAYMENT_METHOD_EMOJIS: Partial<Record<PaymentMethod, string>> = {
  card: '💳',
  transfer: '🏦',
  check: '📝',
  cash: '💵',
}

interface InvoicePaymentFormProps {
  remainingCents: number
  isPending: boolean
  error?: unknown | null
  onSubmit: (data: { amount_cents: number; payment_method: PaymentMethod; payment_date: string; notes?: string }) => void
  onCancel: () => void
}

export function InvoicePaymentForm({
  remainingCents,
  isPending,
  error,
  onSubmit,
  onCancel,
}: InvoicePaymentFormProps) {
  const [paymentAmount, setPaymentAmount] = useState('')
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('card')
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0])
  const [paymentNotes, setPaymentNotes] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

  const cents = paymentAmount ? Math.round(parseFloat(paymentAmount) * 100) : 0
  const isAmountValid = cents > 0 && cents <= remainingCents

  const handleSubmit = () => {
    setValidationError(null)
    if (!paymentAmount) { setValidationError('Montant requis.'); return }
    if (cents <= 0) { setValidationError('Le montant doit être supérieur à 0.'); return }
    if (cents > remainingCents) { setValidationError(`Le montant dépasse le reste dû (${(remainingCents / 100).toFixed(2)} €).`); return }
    if (!paymentDate) { setValidationError('Date requise.'); return }
    onSubmit({ amount_cents: cents, payment_method: paymentMethod, payment_date: paymentDate, notes: paymentNotes || undefined })
  }

  const handleCancel = () => {
    setPaymentAmount('')
    setPaymentNotes('')
    onCancel()
  }

  return (
    <div className="card p-4 space-y-4">
      <h4 className="font-medium flex items-center gap-2">
        <Banknote className="w-4 h-4" />
        Enregistrer un paiement
      </h4>

      {/* Récap */}
      <div className="flex items-center justify-between px-4 py-2 card border border-dark-600">
        <span className="text-sm text-dark-400">Reste à payer</span>
        <span className="text-base font-bold text-primary-400">
          {(remainingCents / 100).toFixed(2)} EUR
        </span>
      </div>

      {error != null && (
        <div className="p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
          {normalizeError(error).message || 'Erreur lors du paiement'}
        </div>
      )}
      {validationError && (
        <div className="p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
          {validationError}
        </div>
      )}

      {/* Mode de paiement — tuiles visuelles */}
      <div>
        <label className="block text-sm text-dark-400 mb-2">Mode de paiement *</label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {(Object.entries(PAYMENT_METHOD_LABELS) as [PaymentMethod, string][]).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setPaymentMethod(value)}
              className={`flex flex-col items-center gap-1 p-4 rounded-xl border font-medium text-xs transition-all ${
                paymentMethod === value
                  ? 'border-primary-500/40 bg-primary-500/10 text-primary-400'
                  : 'border-dark-600 bg-dark-900 text-dark-400 hover:bg-dark-600'
              }`}
            >
              {paymentMethod === value
                ? <Check className="w-3.5 h-3.5 shrink-0" />
                : <span className="text-lg">{PAYMENT_METHOD_EMOJIS[value] ?? '💰'}</span>
              }
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-dark-400 mb-1">Montant (EUR) *</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            max={(remainingCents / 100).toFixed(2)}
            value={paymentAmount}
            onChange={(e) => setPaymentAmount(e.target.value)}
            placeholder={(remainingCents / 100).toFixed(2)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm text-dark-400 mb-1">Date *</label>
          <input
            type="date"
            value={paymentDate}
            onChange={(e) => setPaymentDate(e.target.value)}
            className="input"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm text-dark-400 mb-1">Notes</label>
        <input
          type="text"
          value={paymentNotes}
          onChange={(e) => setPaymentNotes(e.target.value)}
          placeholder="Notes optionnelles..."
          className="input"
        />
      </div>

      <div className="flex gap-2 justify-end">
        <button onClick={handleCancel} className="btn-secondary btn-sm">
          Annuler
        </button>
        <button
          onClick={handleSubmit}
          disabled={isPending || !paymentAmount || !isAmountValid || !paymentDate}
          className="btn-primary btn-sm"
        >
          {isPending ? 'Envoi...' : 'Valider le paiement'}
        </button>
      </div>
    </div>
  )
}
