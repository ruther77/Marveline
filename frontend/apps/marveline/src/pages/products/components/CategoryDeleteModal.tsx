import { useDeleteCategory } from '@/api/queries'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { ActionError } from '@shared/components/ui/ActionError'
import type { Category } from '@/types/product'
import { AlertTriangle } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'

interface CategoryDeleteModalProps {
  isOpen: boolean
  onClose: () => void
  category?: Category | null
}

export function CategoryDeleteModal({
  isOpen,
  onClose,
  category,
}: CategoryDeleteModalProps) {
  const deleteMutation = useDeleteCategory()

  const handleDelete = () => {
    if (category) {
      deleteMutation.mutate(category.id, { onSuccess: onClose })
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Supprimer la catégorie"
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
              Êtes-vous sûr de vouloir supprimer la catégorie{' '}
              <span className="font-semibold">{category?.name}</span> ?
            </p>
            <p className="text-sm text-dark-400 mt-2">
              Cette action est irréversible. Les produits de cette catégorie ne
              seront pas supprimés mais n'auront plus de catégorie assignée.
            </p>
          </div>
        </div>
      </div>
    </Modal>
  )
}
