import { useMutation, useQueryClient } from '@tanstack/react-query'
import { categoriesApi } from '@/api/categories'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { Category } from '@/types/product'
import { AlertTriangle } from 'lucide-react'

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
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: (id: number) => categoriesApi.deleteCategory(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      onClose()
    },
  })

  const handleDelete = () => {
    if (category) {
      deleteMutation.mutate(category.id)
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
        {deleteMutation.error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {(deleteMutation.error as Error).message ||
              'Une erreur est survenue'}
          </div>
        )}

        <div className="flex items-start gap-3">
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
