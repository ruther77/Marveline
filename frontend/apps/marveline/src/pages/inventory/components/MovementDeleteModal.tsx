import { useDeleteMovement } from '@/api/queries'
import { normalizeError } from '@shared/errors/normalizer'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { ActionError } from '@shared/components/ui/ActionError'
import { AlertTriangle } from 'lucide-react'

interface MovementDeleteModalProps {
  isOpen: boolean
  onClose: () => void
  movement?: { id: number; movement_type: string } | null
}

export function MovementDeleteModal({ isOpen, onClose, movement }: MovementDeleteModalProps) {
  const deleteMutation = useDeleteMovement()

  const handleDelete = () => {
    if (movement) {
      deleteMutation.mutate(movement.id, { onSuccess: onClose })
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Supprimer le mouvement"
      size="sm"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={handleDelete}
          cancelText="Annuler"
          confirmText="Supprimer"
          loading={deleteMutation.isPending}
          confirmVariant="danger"
        />
      }
    >
      <div className="space-y-4">
        <ActionError
          message={deleteMutation.error ? (normalizeError(deleteMutation.error).message || 'Une erreur est survenue') : null}
          onDismiss={() => deleteMutation.reset()}
        />

        <div className="flex items-start gap-4">
          <div className="p-2 bg-red-500/10 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-red-500" />
          </div>
          <div className="flex-1">
            <p className="text-dark-200">
              Êtes-vous sûr de vouloir supprimer ce mouvement ?
            </p>
            <p className="text-sm text-dark-400 mt-2">
              Cette action est irréversible.
            </p>
          </div>
        </div>
      </div>
    </Modal>
  )
}
