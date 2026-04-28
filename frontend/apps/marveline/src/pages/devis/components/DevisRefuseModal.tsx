import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { formatCents } from '@/lib/utils'

const REFUSAL_REASONS = [
  'Prix trop élevé',
  'Délai de réponse trop long',
  'Offre concurrente retenue',
  'Projet annulé',
  'Modification du périmètre',
]

interface DevisRefuseModalProps {
  open: boolean
  refuseReason: string
  isPending: boolean
  error?: string | null
  onReasonChange: (value: string) => void
  onClose: () => void
  onConfirm: () => void
  devisNumber?: string
  totalAmountCents?: number
  customerName?: string
}

export function DevisRefuseModal({
  open,
  refuseReason,
  isPending,
  error,
  onReasonChange,
  onClose,
  onConfirm,
  devisNumber,
  totalAmountCents,
  customerName,
}: DevisRefuseModalProps) {
  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Refuser le devis"
      size="sm"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={onConfirm}
          confirmText={isPending ? 'Refus…' : 'Confirmer le refus'}
          confirmVariant="danger"
          loading={isPending}
        />
      }
    >
      <div className="space-y-4">
        {(devisNumber || customerName || totalAmountCents !== undefined) && (
          <div className="bg-dark-900 rounded-lg p-4 text-sm space-y-1">
            {devisNumber && <p className="font-medium">{devisNumber}</p>}
            {customerName && <p className="text-dark-400">{customerName}</p>}
            {totalAmountCents !== undefined && (
              <p className="text-dark-300">
                Total : <span className="font-semibold">{formatCents(totalAmountCents)}</span>
              </p>
            )}
          </div>
        )}
        <div>
          <p className="text-xs text-dark-400 mb-2">Motif rapide</p>
          <div className="flex flex-wrap gap-1.5">
            {REFUSAL_REASONS.map((reason) => (
              <button
                key={reason}
                type="button"
                onClick={() => onReasonChange(refuseReason === reason ? '' : reason)}
                className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                  refuseReason === reason
                    ? 'bg-red-500/15 text-red-400 border-red-500/30'
                    : 'bg-dark-900 text-dark-400 border-dark-600 hover:border-dark-500'
                }`}
              >
                {reason}
              </button>
            ))}
          </div>
        </div>
        <textarea
          rows={3}
          placeholder="Motif du refus (optionnel)…"
          value={refuseReason}
          onChange={(e) => onReasonChange(e.target.value)}
          className="input w-full resize-none"
          autoFocus
        />
        {error != null && (
          <p className="text-red-400 text-sm">{error}</p>
        )}
      </div>
    </Modal>
  )
}
