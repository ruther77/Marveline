import { useState } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { Send } from 'lucide-react'

interface InvoiceMarkSentModalProps {
  invoiceNumber: string
  isPending: boolean
  error?: unknown | null
  onConfirm: (data: { sent_at?: string; notes?: string }) => void
  onClose: () => void
}

export function InvoiceMarkSentModal({
  invoiceNumber,
  isPending,
  error,
  onConfirm,
  onClose,
}: InvoiceMarkSentModalProps) {
  const [sentTo, setSentTo] = useState('')
  const [sendMessage, setSendMessage] = useState('')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="modal-panel w-full max-w-md p-6 space-y-4">
        <h3 className="text-base font-semibold flex items-center gap-2">
          <Send className="w-4 h-4 text-primary-400" />
          Envoyer la facture {invoiceNumber}
        </h3>

        <div>
          <label className="block text-sm text-dark-400 mb-1">Date d'envoi</label>
          <input
            type="date"
            value={sentTo}
            onChange={(e) => setSentTo(e.target.value)}
            className="input"
          />
          <p className="text-xs text-dark-500 mt-1">Laisser vide pour utiliser la date d'aujourd'hui</p>
        </div>

        <div>
          <label className="block text-sm text-dark-400 mb-1">Notes (optionnel)</label>
          <textarea
            value={sendMessage}
            onChange={(e) => setSendMessage(e.target.value)}
            className="input"
            rows={3}
            placeholder="Notes internes sur l'envoi…"
          />
        </div>

        {error != null && (
          <p className="text-red-400 text-sm">
            {normalizeError(error).message || "Erreur lors de l'envoi"}
          </p>
        )}

        <div className="flex gap-4 pt-2">
          <button onClick={onClose} className="btn-secondary flex-1">
            Annuler
          </button>
          <button
            onClick={() => onConfirm({ sent_at: sentTo || undefined, notes: sendMessage || undefined })}
            disabled={isPending}
            className="btn-primary flex-1 flex items-center justify-center gap-2"
          >
            <Send className="w-4 h-4" />
            {isPending ? 'Envoi…' : "Confirmer l'envoi"}
          </button>
        </div>
      </div>
    </div>
  )
}
