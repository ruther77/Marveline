import { ConfirmDialog } from '@shared/components/ui/ConfirmDialog'

interface ArchiveReservationModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  loading?: boolean
  reference?: string
}

export function ArchiveReservationModal({
  isOpen,
  onClose,
  onConfirm,
  loading,
  reference,
}: ArchiveReservationModalProps) {
  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      variant="default"
      title="Archiver cette réservation ?"
      description={
        reference
          ? `La réservation ${reference} sera archivée et masquée des listes courantes. Elle reste consultable.`
          : 'La réservation sera archivée et masquée des listes courantes. Elle reste consultable.'
      }
      confirmText="Archiver"
      cancelText="Annuler"
      loading={loading}
    />
  )
}
