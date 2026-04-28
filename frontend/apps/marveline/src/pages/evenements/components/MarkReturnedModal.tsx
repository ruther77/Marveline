import { useState } from 'react'
import { Modal } from '@shared/components/ui'
import { useUpdateEventStatus } from '@/api/queries/useEvenements'
import { normalizeError } from '@shared/errors/normalizer'
import { CheckCircle } from 'lucide-react'

interface Props {
  open: boolean
  onClose: () => void
  evenementId: number
  evenementName: string
}

export function MarkReturnedModal({ open, onClose, evenementId, evenementName }: Props) {
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)

  const updateStatus = useUpdateEventStatus(evenementId)

  const handleConfirm = () => {
    setError(null)
    updateStatus.mutate({ status: 'returned', notes: notes.trim() || undefined }, {
      onSuccess: () => {
        onClose()
        setNotes('')
      },
      onError: (err) => {
        setError(
          normalizeError(err).message || 'Erreur lors de la mise à jour.'
        )
      },
    })
  }

  const handleClose = () => { setError(null); onClose() }

  return (
    <Modal
      isOpen={open}
      onClose={handleClose}
      title="Confirmer le retour matériel"
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={handleClose} className="text-sm text-dark-400 hover:text-dark-50 px-4 py-2">
            Annuler
          </button>
          <button
            onClick={handleConfirm}
            disabled={updateStatus.isPending}
            className="flex items-center gap-2 bg-green-700 hover:bg-green-800 text-white text-sm font-medium px-6 py-2 rounded-lg disabled:opacity-50"
          >
            <CheckCircle className="w-4 h-4" />
            {updateStatus.isPending ? 'Confirmation…' : 'Confirmer le retour'}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="bg-dark-900/50 rounded-lg px-4 py-4">
          <p className="text-sm font-medium">{evenementName}</p>
          <p className="text-dark-400 text-xs mt-0.5">
            Le statut passera à <span className="text-green-400 font-medium">Retourné</span>
          </p>
        </div>

        <div>
          <label className="block text-sm text-dark-400 mb-1">Notes de retour (optionnel)</label>
          <textarea
            rows={3}
            placeholder="Observations, remarques sur le retour…"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="input"
          />
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>
    </Modal>
  )
}
