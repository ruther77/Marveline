import { useMutation, useQueryClient } from '@tanstack/react-query'
import { eventsApi } from '@/api/events'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { EventItem } from '@/types/event'

interface EventItemDeleteModalProps {
  isOpen: boolean
  onClose: () => void
  eventId: number
  item?: EventItem | null
}

export function EventItemDeleteModal({
  isOpen,
  onClose,
  eventId,
  item,
}: EventItemDeleteModalProps) {
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: () => eventsApi.removeItem(item!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event', eventId] })
      queryClient.invalidateQueries({ queryKey: ['events'] })
      onClose()
    },
  })

  const handleDelete = () => {
    if (item) {
      deleteMutation.mutate()
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Supprimer l'article"
      size="sm"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={handleDelete}
          cancelText="Annuler"
          confirmText="Supprimer"
          confirmVariant="danger"
          loading={deleteMutation.isPending}
        />
      }
    >
      <div className="space-y-4">
        {deleteMutation.error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {(deleteMutation.error as Error).message || 'Une erreur est survenue'}
          </div>
        )}

        <p className="text-dark-300">
          Êtes-vous sûr de vouloir supprimer cet article ?
        </p>

        {item && (
          <div className="p-3 bg-dark-800 rounded-lg border border-dark-700">
            <div className="text-sm text-dark-400">Article</div>
            <div className="font-medium mt-1">
              Quantité: {item.quantity} × {Number(item.unit_price).toFixed(2)} €
            </div>
            <div className="text-green-500 font-bold mt-2">
              Total: {Number(item.total_price).toFixed(2)} €
            </div>
          </div>
        )}

        <p className="text-sm text-red-400">
          Cette action est irréversible.
        </p>
      </div>
    </Modal>
  )
}
