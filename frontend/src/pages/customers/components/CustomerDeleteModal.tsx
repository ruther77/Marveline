import { useMutation, useQueryClient } from '@tanstack/react-query'
import { customersApi } from '@/api/customers'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { CustomerList } from '@/types/customer'
import { AlertTriangle } from 'lucide-react'

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
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: (id: number) => customersApi.deleteCustomer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      onClose()
    },
  })

  const handleDelete = () => {
    if (customer) {
      deleteMutation.mutate(customer.id)
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
        {deleteMutation.error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {(deleteMutation.error as Error).message || 'Une erreur est survenue'}
          </div>
        )}

        <div className="flex items-start gap-3">
          <div className="p-2 bg-red-500/10 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-red-500" />
          </div>
          <div className="flex-1">
            <p className="text-dark-200">
              Etes-vous sur de vouloir supprimer le client{' '}
              <span className="font-semibold">{customer?.display_name}</span> ?
            </p>
            <p className="text-sm text-dark-400 mt-2">
              Cette action est irreversible. Toutes les donnees associees seront
              perdues.
            </p>
          </div>
        </div>
      </div>
    </Modal>
  )
}
