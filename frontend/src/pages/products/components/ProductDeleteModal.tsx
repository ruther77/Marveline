import { useMutation, useQueryClient } from '@tanstack/react-query'
import { productsApi } from '@/api/products'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { Product } from '@/types/product'
import { AlertTriangle } from 'lucide-react'

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
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: (id: number) => productsApi.deleteProduct(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      onClose()
    },
  })

  const handleDelete = () => {
    if (product) {
      deleteMutation.mutate(product.id)
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
