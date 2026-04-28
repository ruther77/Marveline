import { useState } from 'react'
import { ScrollText } from 'lucide-react'
import { formatDate, formatCents } from '@/lib/utils'
import type { CreditNote } from '@/types/invoice'

interface CreditNoteCreate {
  amount_cents: number
  reason: string
  issue_date: string
}

interface InvoiceCreditNotesSectionProps {
  status: string
  creditNotes: CreditNote[]
  isPending: boolean
  onSubmit: (data: CreditNoteCreate) => void
}

export function InvoiceCreditNotesSection({
  status,
  creditNotes,
  isPending,
  onSubmit,
}: InvoiceCreditNotesSectionProps) {
  const [showForm, setShowForm] = useState(false)
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [issueDate, setIssueDate] = useState(new Date().toISOString().split('T')[0])

  const handleSubmit = () => {
    if (!reason.trim() || !amount) return
    const cents = Math.round(parseFloat(amount) * 100)
    if (cents <= 0) return
    onSubmit({ amount_cents: cents, reason: reason.trim(), issue_date: issueDate })
    setShowForm(false)
    setAmount('')
    setReason('')
  }

  const handleCancel = () => {
    setShowForm(false)
    setAmount('')
    setReason('')
  }

  return (
    <div className="border-t border-dark-600 pt-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h4 className="font-medium flex items-center gap-2 text-sm">
          <ScrollText className="w-4 h-4 text-dark-400" />
          Avoirs
          {creditNotes.length > 0 && (
            <span className="text-xs bg-dark-900 text-dark-300 px-1.5 py-0.5 rounded">
              {creditNotes.length}
            </span>
          )}
        </h4>
        {status !== 'cancelled' && (
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn-secondary btn-sm text-xs"
          >
            + Avoir
          </button>
        )}
      </div>

      {creditNotes.length > 0 && (
        <div className="space-y-2">
          {creditNotes.map((cn) => (
            <div key={cn.id} className="flex items-center justify-between bg-dark-900 rounded-lg px-4 py-2 text-sm">
              <div>
                <span className="font-mono text-xs text-dark-400 mr-2">{cn.invoice_number}</span>
                <span className="text-dark-300">{cn.reason}</span>
              </div>
              <div className="text-right">
                <span className="text-purple-400 font-medium">-{formatCents(cn.amount_cents)}</span>
                <span className="ml-2 text-xs text-dark-500">{formatDate(cn.issue_date)}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="bg-dark-900 rounded-lg p-4 space-y-4 border border-dark-600">
          <p className="text-sm font-medium text-dark-200">Nouvel avoir</p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-dark-400 mb-1">Montant (EUR)</label>
              <input
                type="number"
                min="0.01"
                step="0.01"
                placeholder="0.00"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-xs text-dark-400 mb-1">Date d'émission</label>
              <input
                type="date"
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                className="input"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-dark-400 mb-1">Motif (min. 5 caractères)</label>
            <input
              type="text"
              placeholder="Motif de l'avoir…"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="input"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={handleCancel} className="btn-secondary btn-sm">
              Annuler
            </button>
            <button
              onClick={handleSubmit}
              disabled={isPending || !reason.trim() || reason.trim().length < 5 || !amount}
              className="btn-primary btn-sm"
            >
              {isPending ? 'Création...' : "Créer l'avoir"}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
