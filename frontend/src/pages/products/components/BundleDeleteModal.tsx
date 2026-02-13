import { useMutation, useQueryClient } from '@tanstack/react-query'
import { bundlesApi } from '@/api/bundles'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { Bundle } from '@/types/product'
import { AlertTriangle } from 'lucide-react'

interface BundleDeleteModalProps {
  isOpen: boolean
  onClose: () => void
  bundle?: Bundle | null
}

export function BundleDeleteModal({
  isOpen,
  onClose,
  bundle,
}: BundleDeleteModalProps) {
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: (id: number) => bundlesApi.deleteBundle(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bundles'] })
      onClose()
    },
  })

  const handleDelete = () => {
    if (bundle) {
      deleteMutation.mutate(bundle.id)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Supprimer la formule"
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
              Êtes-vous sûr de vouloir supprimer la formule{' '}
              <span className="font-semibold">{bundle?.name}</span> ?
            </p>
            <p className="text-sm text-dark-400 mt-2">
              Cette action est irréversible. Tous les produits inclus dans cette
              formule ne seront pas supprimés.
            </p>
          </div>
        </div>
      </div>
    </Modal>
  )
}
