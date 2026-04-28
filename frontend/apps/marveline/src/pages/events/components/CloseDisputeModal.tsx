import { useState } from 'react'
import { Modal } from '@shared/components/ui/Modal'
import { Textarea } from '@shared/components/ui/Textarea'
import { Button } from '@shared/components/ui/Button'

interface CloseDisputeModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (resolutionNotes: string) => void
  loading?: boolean
  error?: string | null
}

export function CloseDisputeModal({
  isOpen,
  onClose,
  onConfirm,
  loading = false,
  error = null,
}: CloseDisputeModalProps) {
  const [notes, setNotes] = useState('')

  const handleSubmit = () => {
    const cleaned = notes.trim()
    if (!cleaned) return
    onConfirm(cleaned)
  }

  const handleClose = () => {
    setNotes('')
    onClose()
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} size="sm" title="Clore le litige">
      <div className="space-y-4">
        <Textarea
          label="Notes de résolution"
          placeholder="Décrivez la résolution du litige…"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={4}
        />
        {error != null && <p className="text-sm text-red-400">{error}</p>}
        <div className="flex justify-end gap-4">
          <Button variant="ghost" onClick={handleClose} disabled={loading}>
            Annuler
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            loading={loading}
            disabled={!notes.trim() || loading}
          >
            Clore le litige
          </Button>
        </div>
      </div>
    </Modal>
  )
}
