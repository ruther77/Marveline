import { useDeleteDeliveryZone } from '@/api/queries'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { ActionError } from '@shared/components/ui/ActionError'
import type { DeliveryZone } from '@/types/delivery_zone'
import { AlertTriangle } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'

interface DeliveryZoneDeleteModalProps {
  isOpen: boolean
  onClose: () => void
  zone?: DeliveryZone | null
}

export function DeliveryZoneDeleteModal({
  isOpen,
  onClose,
  zone,
}: DeliveryZoneDeleteModalProps) {
  const deleteMutation = useDeleteDeliveryZone()

  const handleDelete = () => {
    if (zone) {
      deleteMutation.mutate(zone.id, { onSuccess: onClose })
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Supprimer la zone de livraison"
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
              Êtes-vous sûr de vouloir supprimer la zone{' '}
              <span className="font-semibold">
                {zone?.department_name} ({zone?.department_code})
              </span>{' '}
              ?
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
