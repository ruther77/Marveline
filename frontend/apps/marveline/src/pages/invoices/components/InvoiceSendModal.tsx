import { useState } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { Modal } from '@shared/components/ui/Modal'
import { useMarkInvoiceSent } from '@/api/queries/useInvoices'
import { Send, Mail, FileText } from 'lucide-react'
import { formatCents } from '@/lib/utils'
import type { InvoiceListItem } from '@/types/invoice'

interface InvoiceSendModalProps {
  isOpen: boolean
  onClose: () => void
  invoice: InvoiceListItem | null
}

export function InvoiceSendModal({ isOpen, onClose, invoice }: InvoiceSendModalProps) {
  const [notes, setNotes] = useState('')
  const [sentAt, setSentAt] = useState(new Date().toISOString().split('T')[0])
  const [error, setError] = useState<string | null>(null)
  const markSentMutation = useMarkInvoiceSent(invoice?.id ?? 0)

  const handleClose = () => {
    setNotes('')
    setSentAt(new Date().toISOString().split('T')[0])
    setError(null)
    onClose()
  }

  const handleSubmit = async () => {
    if (!invoice || markSentMutation.isPending) return
    setError(null)
    try {
      await markSentMutation.mutateAsync({
        sent_at: sentAt,
        notes: notes || undefined,
      })
      handleClose()
    } catch (err) {
      setError(normalizeError(err).message || "Erreur lors de l'envoi de la facture.")
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Marquer comme envoyée"
      size="sm"
    >
      {invoice && (
        <div className="space-y-4">
          {/* Preview miniature facture */}
          <div className="rounded-xl border border-dark-600 bg-dark-900 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 bg-dark-900/50 border-b border-dark-600">
              <div className="flex items-center gap-2">
                <FileText className="w-3.5 h-3.5 text-dark-400" />
                <span className="text-xs text-dark-400 uppercase tracking-wide">Aperçu facture</span>
              </div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-dark-900 text-dark-300 capitalize">
                {invoice.status}
              </span>
            </div>
            <div className="px-4 py-4 space-y-2">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-sm font-semibold truncate">{invoice.invoice_number}</p>
                <p className="text-base font-bold shrink-0">{formatCents(invoice.total_amount_cents)}</p>
              </div>
              <div className="flex items-center justify-between text-xs text-dark-400">
                <span className="truncate">{invoice.customer_name || '—'}</span>
                <span className="shrink-0">Éch. : {invoice.due_date}</span>
              </div>
              {invoice.paid_amount_cents > 0 && (
                <div className="pt-1.5 border-t border-dark-600 flex justify-between text-xs">
                  <span className="text-dark-400">Déjà réglé</span>
                  <span className="text-green-400">{formatCents(invoice.paid_amount_cents)}</span>
                </div>
              )}
            </div>
          </div>

          <div className="p-4 card">
            <div className="flex items-center gap-2 text-sm">
              <Mail className="w-4 h-4 text-dark-400 shrink-0" />
              <div>
                <span className="text-dark-400">Destinataire : </span>
                <span className="font-medium">{invoice.customer_name || '—'}</span>
              </div>
            </div>
            <div className="mt-1 text-xs text-dark-500 pl-6">
              Facture {invoice.invoice_number}
            </div>
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">Date d'envoi</label>
            <input
              type="date"
              value={sentAt}
              onChange={(e) => setSentAt(e.target.value)}
              className="input"
            />
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">Notes internes (optionnel)</label>
            <textarea
              rows={3}
              placeholder="Ex : Envoyé par email le…"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="input"
            />
          </div>

          {error && (
            <div className="p-4 bg-red-900/20 border border-red-700 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-4 pt-1">
            <button
              onClick={handleClose}
              disabled={markSentMutation.isPending}
              className="btn-secondary"
            >
              Annuler
            </button>
            <button
              onClick={handleSubmit}
              disabled={markSentMutation.isPending}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm px-4 py-2 rounded-lg disabled:opacity-60"
            >
              <Send className="w-4 h-4" />
              {markSentMutation.isPending ? 'Envoi…' : 'Marquer comme envoyée'}
            </button>
          </div>
        </div>
      )}
    </Modal>
  )
}
