import { ConfirmDialog } from '@shared/components/ui/ConfirmDialog'

interface DeleteReservationModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  loading?: boolean
  reference?: string
}

export function DeleteReservationModal({
  isOpen,
  onClose,
  onConfirm,
  loading,
  reference,
}: DeleteReservationModalProps) {
  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      variant="danger"
      title="Supprimer cette réservation ?"
      description={
        reference
          ? `La réservation ${reference} sera définitivement supprimée. Cette action est irréversible.`
          : 'La réservation sera définitivement supprimée. Cette action est irréversible.'
      }
      confirmText="Supprimer"
      cancelText="Annuler"
      loading={loading}
    />
  )
}
