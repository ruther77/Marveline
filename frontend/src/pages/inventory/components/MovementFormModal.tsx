import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { inventoryApi } from '@/api/inventory'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { InventoryMovement, CreateMovementRequest, UpdateMovementRequest } from '@/types/inventory'

const movementSchema = z.object({
  movement_type: z.enum(['departure', 'return']),
  scheduled_date: z.string().min(1, 'Date requise'),
  delivery_method: z.enum(['delivery', 'pickup', 'shipping']).optional(),
  delivery_address: z.string().optional(),
  delivery_notes: z.string().optional(),
})

type FormData = z.infer<typeof movementSchema>

interface MovementFormModalProps {
  isOpen: boolean
  onClose: () => void
  movement?: Partial<InventoryMovement> | null
  mode: 'create' | 'edit'
}

export function MovementFormModal({ isOpen, onClose, movement, mode }: MovementFormModalProps) {
  const queryClient = useQueryClient()
  const isEdit = mode === 'edit'

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(movementSchema),
  })

  useEffect(() => {
    if (isOpen && movement) {
      reset({
        movement_type: movement.movement_type || 'departure',
        scheduled_date: movement.scheduled_date?.split('T')[0] || '',
        delivery_method: movement.delivery_method,
        delivery_address: movement.delivery_address || '',
        delivery_notes: movement.delivery_notes || '',
      })
    } else if (isOpen) {
      reset({
        movement_type: 'departure',
        scheduled_date: '',
        delivery_method: 'delivery',
      })
    }
  }, [isOpen, movement, reset])

  const createMutation = useMutation({
    mutationFn: (data: CreateMovementRequest) => inventoryApi.createMovement(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory-movements'] })
      onClose()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateMovementRequest }) =>
      inventoryApi.updateMovement(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory-movements'] })
      onClose()
    },
  })

  const onSubmit = (data: FormData) => {
    const cleanData = {
      ...data,
      items: [],
    }

    if (isEdit && movement?.id) {
      updateMutation.mutate({ id: movement.id, data: cleanData as UpdateMovementRequest })
    } else {
      createMutation.mutate(cleanData as CreateMovementRequest)
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier le mouvement' : 'Nouveau mouvement'}
      size="md"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={handleSubmit(onSubmit)}
          cancelText="Annuler"
          confirmText={isEdit ? 'Enregistrer' : 'Créer'}
          loading={isLoading}
        />
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {(error as Error).message || 'Une erreur est survenue'}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Type *</label>
          <select {...register('movement_type')} className="input w-full">
            <option value="departure">Départ</option>
            <option value="return">Retour</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Date prévue *</label>
          <input {...register('scheduled_date')} type="date" className="input w-full" />
          {errors.scheduled_date && (
            <p className="text-red-500 text-sm mt-1">{errors.scheduled_date.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Méthode de livraison</label>
          <select {...register('delivery_method')} className="input w-full">
            <option value="">Non spécifié</option>
            <option value="delivery">Livraison</option>
            <option value="pickup">Enlèvement</option>
            <option value="shipping">Expédition</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Adresse de livraison</label>
          <textarea {...register('delivery_address')} className="input w-full" rows={2} />
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Notes</label>
          <textarea {...register('delivery_notes')} className="input w-full" rows={3} />
        </div>
      </form>
    </Modal>
  )
}
