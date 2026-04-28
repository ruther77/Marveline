import { ConfirmDialog } from '@shared/components/ui/ConfirmDialog'

interface CancelReservationModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  loading?: boolean
  reference?: string
}

export function CancelReservationModal({
  isOpen,
  onClose,
  onConfirm,
  loading,
  reference,
}: CancelReservationModalProps) {
  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      variant="danger"
      title="Annuler cette réservation ?"
      description={
        reference
          ? `La réservation ${reference} sera annulée. Cette action est irréversible.`
          : 'La réservation sera annulée. Cette action est irréversible.'
      }
      confirmText="Oui, annuler"
      cancelText="Retour"
      loading={loading}
    />
  )
}
