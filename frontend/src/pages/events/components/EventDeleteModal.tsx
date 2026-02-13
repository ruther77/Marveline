import { useMutation, useQueryClient } from '@tanstack/react-query'
import { eventsApi } from '@/api/events'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { AlertTriangle } from 'lucide-react'

interface EventDeleteModalProps {
  isOpen: boolean
  onClose: () => void
  event?: { id: number; customer_name: string } | null
}

export function EventDeleteModal({ isOpen, onClose, event }: EventDeleteModalProps) {
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: (id: number) => eventsApi.deleteEvent(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      queryClient.invalidateQueries({ queryKey: ['events-stats'] })
      onClose()
    },
  })

  const handleDelete = () => {
    if (event) {
      deleteMutation.mutate(event.id)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Supprimer l'événement"
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
              Êtes-vous sûr de vouloir supprimer l'événement de{' '}
              <span className="font-semibold">{event?.customer_name}</span> ?
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
