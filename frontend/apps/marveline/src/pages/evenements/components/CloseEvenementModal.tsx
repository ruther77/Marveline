import { useState } from 'react'
import { Modal } from '@shared/components/ui'
import { useCloseEvenement } from '@/api/queries/useEvenements'
import { normalizeError } from '@shared/errors/normalizer'
import { Lock } from 'lucide-react'

const MIN_NOTES_LENGTH = 10

interface Props {
  open: boolean
  onClose: () => void
  evenementId: number
  evenementName: string
}

export function CloseEvenementModal({ open, onClose, evenementId, evenementName }: Props) {
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)

  const closeEvenement = useCloseEvenement(evenementId)

  const isValid = notes.trim().length >= MIN_NOTES_LENGTH

  const handleConfirm = () => {
    if (!isValid) return
    setError(null)
    closeEvenement.mutate(notes.trim(), {
      onSuccess: () => {
        onClose()
        setNotes('')
      },
      onError: (err) => {
        setError(normalizeError(err).message || 'Erreur lors de la clôture.')
      },
    })
  }

  const handleClose = () => { setError(null); onClose() }

  return (
    <Modal
      isOpen={open}
      onClose={handleClose}
      title="Clôturer l'événement"
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={handleClose} className="text-sm text-dark-400 hover:text-dark-50 px-4 py-2">
            Annuler
          </button>
          <button
            onClick={handleConfirm}
            disabled={!isValid || closeEvenement.isPending}
            className="flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium px-6 py-2 rounded-lg disabled:opacity-50"
          >
            <Lock className="w-4 h-4" />
            {closeEvenement.isPending ? 'Clôture…' : 'Clôturer'}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="bg-dark-900/50 rounded-lg px-4 py-4">
          <p className="text-sm font-medium">{evenementName}</p>
          <p className="text-dark-400 text-xs mt-0.5">
            Le statut passera à <span className="text-primary-400 font-medium">Clôturé</span>. Cette action est irréversible.
          </p>
        </div>

        <div>
          <label className="block text-sm text-dark-400 mb-1">
            Notes de clôture <span className="text-red-400">*</span>
            <span className="text-dark-500 ml-1">(min. {MIN_NOTES_LENGTH} caractères)</span>
          </label>
          <textarea
            rows={4}
            placeholder="Résumé de l'événement, observations finales, bilan…"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="input"
          />
          <p className="text-xs text-dark-500 mt-1">{notes.trim().length} / {MIN_NOTES_LENGTH} min</p>
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>
    </Modal>
  )
}
