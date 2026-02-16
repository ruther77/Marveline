import { useEffect } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { inventoryApi } from '@/api/inventory'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { Plus, Trash2 } from 'lucide-react'
import type { InventoryMovement, CreateMovementRequest, UpdateMovementRequest } from '@/types/inventory'

const itemSchema = z.object({
  product_id: z.coerce.number().min(1, 'Produit requis'),
  quantity_expected: z.coerce.number().min(1, 'Quantite >= 1'),
})

const movementSchema = z.object({
  movement_type: z.enum(['departure', 'return']),
  scheduled_date: z.string().min(1, 'Date requise'),
  delivery_method: z.enum(['delivery', 'pickup', 'shipping']).optional(),
  delivery_address: z.string().optional(),
  delivery_notes: z.string().optional(),
  items: z.array(itemSchema).min(1, 'Au moins un article requis'),
})

const editSchema = movementSchema.omit({ items: true })

type CreateFormData = z.infer<typeof movementSchema>
type EditFormData = z.infer<typeof editSchema>
type FormData = CreateFormData

interface MovementFormModalProps {
  isOpen: boolean
  onClose: () => void
  movement?: Partial<InventoryMovement> | null
  mode: 'create' | 'edit'
}

export function MovementFormModal({ isOpen, onClose, movement, mode }: MovementFormModalProps) {
  const queryClient = useQueryClient()
  const isEdit = mode === 'edit'

  const { register, handleSubmit, reset, control, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(isEdit ? editSchema as unknown as z.ZodType<FormData> : movementSchema),
    defaultValues: {
      items: [{ product_id: 0, quantity_expected: 1 }],
    },
  })

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'items',
  })

  useEffect(() => {
    if (isOpen && movement) {
      reset({
        movement_type: movement.movement_type || 'departure',
        scheduled_date: movement.scheduled_date?.split('T')[0] || '',
        delivery_method: movement.delivery_method,
        delivery_address: movement.delivery_address || '',
        delivery_notes: movement.delivery_notes || '',
        items: [{ product_id: 0, quantity_expected: 1 }],
      })
    } else if (isOpen) {
      reset({
        movement_type: 'departure',
        scheduled_date: '',
        delivery_method: 'delivery',
        items: [{ product_id: 0, quantity_expected: 1 }],
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
    if (isEdit && movement?.id) {
      const { items: _items, ...editData } = data
      updateMutation.mutate({ id: movement.id, data: editData as UpdateMovementRequest })
    } else {
      createMutation.mutate({
        movement_type: data.movement_type,
        scheduled_date: data.scheduled_date,
        delivery_method: data.delivery_method,
        delivery_address: data.delivery_address,
        delivery_notes: data.delivery_notes,
        items: data.items.map((item) => ({
          product_id: item.product_id,
          quantity_expected: item.quantity_expected,
        })),
      })
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier le mouvement' : 'Nouveau mouvement'}
      size="lg"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={handleSubmit(onSubmit)}
          cancelText="Annuler"
          confirmText={isEdit ? 'Enregistrer' : 'Creer'}
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
            <option value="departure">Depart</option>
            <option value="return">Retour</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Date prevue *</label>
          <input {...register('scheduled_date')} type="date" className="input w-full" />
          {errors.scheduled_date && (
            <p className="text-red-500 text-sm mt-1">{errors.scheduled_date.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Methode de livraison</label>
          <select {...register('delivery_method')} className="input w-full">
            <option value="">Non specifie</option>
            <option value="delivery">Livraison</option>
            <option value="pickup">Enlevement</option>
            <option value="shipping">Expedition</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Adresse de livraison</label>
          <textarea {...register('delivery_address')} className="input w-full" rows={2} />
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">Notes</label>
          <textarea {...register('delivery_notes')} className="input w-full" rows={2} />
        </div>

        {/* Items section — only shown on create */}
        {!isEdit && (
          <div className="border-t border-dark-700 pt-4">
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-medium text-dark-300">Articles *</label>
              <button
                type="button"
                onClick={() => append({ product_id: 0, quantity_expected: 1 })}
                className="btn-secondary btn-sm flex items-center gap-1"
              >
                <Plus className="w-3 h-3" />
                Ajouter
              </button>
            </div>

            {errors.items && typeof errors.items.message === 'string' && (
              <p className="text-red-500 text-sm mb-2">{errors.items.message}</p>
            )}

            <div className="space-y-2">
              {fields.map((field, index) => (
                <div key={field.id} className="flex gap-2 items-start">
                  <div className="flex-1">
                    <input
                      {...register(`items.${index}.product_id`)}
                      type="number"
                      placeholder="ID produit"
                      className="input w-full"
                    />
                    {errors.items?.[index]?.product_id && (
                      <p className="text-red-500 text-xs mt-1">
                        {errors.items[index]?.product_id?.message}
                      </p>
                    )}
                  </div>
                  <div className="w-24">
                    <input
                      {...register(`items.${index}.quantity_expected`)}
                      type="number"
                      min={1}
                      placeholder="Qte"
                      className="input w-full"
                    />
                    {errors.items?.[index]?.quantity_expected && (
                      <p className="text-red-500 text-xs mt-1">
                        {errors.items[index]?.quantity_expected?.message}
                      </p>
                    )}
                  </div>
                  {fields.length > 1 && (
                    <button
                      type="button"
                      onClick={() => remove(index)}
                      className="p-2 text-dark-400 hover:text-red-400"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </form>
    </Modal>
  )
}
