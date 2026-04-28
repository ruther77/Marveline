import { useDeleteProduct } from '@/api/queries'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { ActionError } from '@shared/components/ui/ActionError'
import type { Product } from '@/types/product'
import { AlertTriangle } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'

interface ProductDeleteModalProps {
  isOpen: boolean
  onClose: () => void
  product?: Product | null
}

export function ProductDeleteModal({
  isOpen,
  onClose,
  product,
}: ProductDeleteModalProps) {
  const deleteMutation = useDeleteProduct()

  const handleDelete = () => {
    if (product) {
      deleteMutation.mutate(product.id, { onSuccess: onClose })
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Supprimer le produit"
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
              Êtes-vous sûr de vouloir supprimer le produit{' '}
              <span className="font-semibold">{product?.name}</span> ?
            </p>
            <p className="text-sm text-dark-400 mt-2">
              Cette action est irréversible. Toutes les données associées seront
              perdues.
            </p>
          </div>
        </div>
      </div>
    </Modal>
  )
}
