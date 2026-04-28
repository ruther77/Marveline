import { useEffect } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { useForm, useFieldArray, useWatch, Control } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useCreateMovement, useUpdateMovement, useProductsList, useProductVariantsList } from '@/api/queries'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { Plus, Trash2 } from 'lucide-react'
import { PAGE_SIZE_SELECT } from '@/lib/constants'
import type { InventoryMovement, CreateMovementRequest, UpdateMovementRequest } from '@/types/inventory'

const itemSchema = z.object({
  product_id: z.coerce.number().min(1, 'Produit requis'),
  variant_id: z.coerce.number().optional(),
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

// Sub-component: renders one item row with dynamic variant select
interface ItemRowProps {
  index: number
  control: Control<FormData>
  register: ReturnType<typeof useForm<FormData>>['register']
  errors: ReturnType<typeof useForm<FormData>>['formState']['errors']
  onRemove: () => void
  showRemove: boolean
  products: { id: number; name: string; sku: string; available_quantity: number }[]
}

function ItemRow({ index, control, register, errors, onRemove, showRemove, products }: ItemRowProps) {
  const selectedProductId = useWatch({ control, name: `items.${index}.product_id` })
  const productId = Number(selectedProductId) || null
  const { data: variants = [] } = useProductVariantsList(productId && productId > 0 ? productId : null)

  return (
    <div className="flex flex-col sm:flex-row gap-2 items-start">
      {/* Product select */}
      <div className="flex-1 w-full sm:w-auto">
        <select
          {...register(`items.${index}.product_id`)}
          className="input"
        >
          <option value="0">-- Choisir un produit --</option>
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.sku}) — dispo: {p.available_quantity}
            </option>
          ))}
        </select>
        {errors.items?.[index]?.product_id && (
          <p className="text-red-500 text-xs mt-1">
            {errors.items[index]?.product_id?.message}
          </p>
        )}
      </div>

      <div className="flex gap-2 items-start w-full sm:w-auto">
        {/* Variant select — only shown when product has variants */}
        {variants.length > 0 && (
          <div className="flex-1 sm:w-36">
            <select
              {...register(`items.${index}.variant_id`)}
              className="input"
            >
              <option value="">Toutes variantes</option>
              {variants.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label} — dispo: {v.available_quantity}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Quantity */}
        <div className="flex-1 sm:w-24">
          <input
            {...register(`items.${index}.quantity_expected`)}
            type="number"
            min={1}
            placeholder="Qté"
            className="input"
          />
          {errors.items?.[index]?.quantity_expected && (
            <p className="text-red-500 text-xs mt-1">
              {errors.items[index]?.quantity_expected?.message}
            </p>
          )}
        </div>

        {showRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-red-400 shrink-0 rounded"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  )
}

interface MovementFormModalProps {
  isOpen: boolean
  onClose: () => void
  movement?: Partial<InventoryMovement> | null
  mode: 'create' | 'edit'
}

export function MovementFormModal({ isOpen, onClose, movement, mode }: MovementFormModalProps) {
  const isEdit = mode === 'edit'

  const { data: productsData } = useProductsList({ active_only: true, limit: PAGE_SIZE_SELECT })
  const products = productsData?.items ?? []

  const { register, handleSubmit, reset, control, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(isEdit ? editSchema as unknown as z.ZodType<FormData> : movementSchema),
    defaultValues: {
      items: [{ product_id: 0, variant_id: undefined, quantity_expected: 1 }],
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
        items: [{ product_id: 0, variant_id: undefined, quantity_expected: 1 }],
      })
    } else if (isOpen) {
      reset({
        movement_type: 'departure',
        scheduled_date: new Date().toISOString().split('T')[0],
        delivery_method: 'delivery',
        items: [{ product_id: 0, variant_id: undefined, quantity_expected: 1 }],
      })
    }
  }, [isOpen, movement, reset])

  const createMutation = useCreateMovement()
  const updateMutation = useUpdateMovement()

  const onSubmit = (data: FormData) => {
    if (isEdit && movement?.id) {
      const { items: _items, ...editData } = data
      updateMutation.mutate({ id: movement.id, data: editData as UpdateMovementRequest }, { onSuccess: onClose })
    } else {
      createMutation.mutate({
        movement_type: data.movement_type,
        scheduled_date: data.scheduled_date,
        delivery_method: data.delivery_method,
        delivery_address: data.delivery_address,
        delivery_notes: data.delivery_notes,
        items: data.items.map((item) => ({
          product_id: item.product_id,
          ...(item.variant_id ? { variant_id: item.variant_id } : {}),
          quantity_expected: item.quantity_expected,
        })),
      }, { onSuccess: onClose })
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
          confirmText={isEdit ? 'Enregistrer' : 'Créer'}
          loading={isLoading}
        />
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {normalizeError(error).message || 'Une erreur est survenue'}
          </div>
        )}

        <div>
          <label htmlFor="movement_type" className="block text-sm text-dark-400 mb-1">Type *</label>
          <select id="movement_type" {...register('movement_type')} className="input">
            <option value="departure">Depart</option>
            <option value="return">Retour</option>
          </select>
        </div>

        <div>
          <label htmlFor="scheduled_date" className="block text-sm text-dark-400 mb-1">Date prevue *</label>
          <input id="scheduled_date" {...register('scheduled_date')} type="date" className="input" />
          {errors.scheduled_date && (
            <p className="text-red-500 text-sm mt-1">{errors.scheduled_date.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="delivery_method" className="block text-sm text-dark-400 mb-1">Methode de livraison</label>
          <select id="delivery_method" {...register('delivery_method')} className="input">
            <option value="">Non specifie</option>
            <option value="delivery">Livraison</option>
            <option value="pickup">Enlevement</option>
            <option value="shipping">Expedition</option>
          </select>
        </div>

        <div>
          <label htmlFor="delivery_address" className="block text-sm text-dark-400 mb-1">Adresse de livraison</label>
          <textarea id="delivery_address" {...register('delivery_address')} className="input" rows={2} />
        </div>

        <div>
          <label htmlFor="delivery_notes" className="block text-sm text-dark-400 mb-1">Notes</label>
          <textarea id="delivery_notes" {...register('delivery_notes')} className="input" rows={2} />
        </div>

        {/* Items section — only shown on create */}
        {!isEdit && (
          <div className="border-t border-dark-600 pt-4">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-medium text-dark-300">Articles *</span>
              <button
                type="button"
                onClick={() => append({ product_id: 0, variant_id: undefined, quantity_expected: 1 })}
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
                <ItemRow
                  key={field.id}
                  index={index}
                  control={control}
                  register={register}
                  errors={errors}
                  products={products}
                  onRemove={() => remove(index)}
                  showRemove={fields.length > 1}
                />
              ))}
            </div>
          </div>
        )}
      </form>
    </Modal>
  )
}
