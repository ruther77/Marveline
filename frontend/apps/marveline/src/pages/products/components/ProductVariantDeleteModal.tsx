import { useDeleteProductVariant } from '@/api/queries'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { ActionError } from '@shared/components/ui/ActionError'
import type { ProductVariant } from '@/types/product_variant'
import { AlertTriangle } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'

interface ProductVariantDeleteModalProps {
  isOpen: boolean
  onClose: () => void
  variant?: ProductVariant | null
  productId: number
}

export function ProductVariantDeleteModal({
  isOpen,
  onClose,
  variant,
  productId,
}: ProductVariantDeleteModalProps) {
  const deleteMutation = useDeleteProductVariant(productId)

  const handleDelete = () => {
    if (variant) {
      deleteMutation.mutate(variant.id, { onSuccess: onClose })
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Supprimer la variante"
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
              Êtes-vous sûr de vouloir supprimer la variante{' '}
              <span className="font-semibold capitalize">{variant?.color}</span>{' '}
              ({variant?.sku}) ?
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
