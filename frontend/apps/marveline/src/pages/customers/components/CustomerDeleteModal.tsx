import { useDeleteCustomer } from '@/api/queries'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { ActionError } from '@shared/components/ui/ActionError'
import type { CustomerList } from '@/types/customer'
import { AlertTriangle } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'

interface CustomerDeleteModalProps {
  isOpen: boolean
  onClose: () => void
  customer?: CustomerList | null
}

export function CustomerDeleteModal({
  isOpen,
  onClose,
  customer,
}: CustomerDeleteModalProps) {
  const deleteMutation = useDeleteCustomer()

  const handleDelete = () => {
    if (customer) {
      deleteMutation.mutate(customer.id, { onSuccess: onClose })
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Supprimer le client"
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
              Désactiver le client{' '}
              <span className="font-semibold">{customer?.display_name}</span> ?
            </p>
            <p className="text-sm text-dark-400 mt-2">
              Le client sera masqué de la liste. Les réservations et factures
              associées sont conservées et restent accessibles.
            </p>
          </div>
        </div>
      </div>
    </Modal>
  )
}
