import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { eventsApi } from '@/api/events'
import { productsApi } from '@/api/products'
import { bundlesApi } from '@/api/bundles'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { EventItem } from '@/types/event'

const eventItemSchema = z.object({
  item_type: z.enum(['product', 'bundle']),
  product_id: z.number().optional(),
  bundle_id: z.number().optional(),
  quantity: z.number().min(1, 'Quantité minimale: 1'),
  unit_price: z.number().min(0, 'Prix invalide'),
  cleaning_fee: z.number().min(0, 'Frais invalides').default(0),
  tax_rate: z.number().min(0, 'TVA invalide').max(100, 'TVA max: 100%').default(20),
  notes: z.string().optional(),
}).refine(
  (data) => data.product_id || data.bundle_id,
  { message: 'Sélectionnez un produit ou une formule', path: ['product_id'] }
)

type FormData = z.infer<typeof eventItemSchema>

interface EventItemFormModalProps {
  isOpen: boolean
  onClose: () => void
  eventId: number
  item?: EventItem | null
  mode: 'create' | 'edit'
}

export function EventItemFormModal({
  isOpen,
  onClose,
  eventId,
  item,
  mode,
}: EventItemFormModalProps) {
  const queryClient = useQueryClient()
  const isEdit = mode === 'edit'
  const [itemType, setItemType] = useState<'product' | 'bundle'>('product')

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(eventItemSchema),
    defaultValues: {
      item_type: 'product',
      quantity: 1,
      unit_price: 0,
      cleaning_fee: 0,
      tax_rate: 20,
    },
  })

  // Charger les produits et bundles
  const { data: productsData } = useQuery({
    queryKey: ['products'],
    queryFn: () => productsApi.getProducts({ page: 1, page_size: 100 }),
    enabled: isOpen,
  })

  const { data: bundlesData } = useQuery({
    queryKey: ['bundles'],
    queryFn: () => bundlesApi.getBundles({ page: 1, page_size: 100 }),
    enabled: isOpen,
  })

  const products = productsData?.items || []
  const bundles = bundlesData?.items || []

  // Mettre à jour le prix quand on sélectionne un produit/bundle
  const selectedProductId = watch('product_id')
  const selectedBundleId = watch('bundle_id')

  useEffect(() => {
    if (itemType === 'product' && selectedProductId) {
      const product = products.find((p) => p.id === selectedProductId)
      if (product) {
        setValue('unit_price', Number(product.base_price))
      }
    } else if (itemType === 'bundle' && selectedBundleId) {
      const bundle = bundles.find((b) => b.id === selectedBundleId)
      if (bundle) {
        setValue('unit_price', Number(bundle.bundle_price))
        setValue('cleaning_fee', Number(bundle.cleaning_fee))
      }
    }
  }, [selectedProductId, selectedBundleId, itemType, products, bundles, setValue])

  useEffect(() => {
    if (isOpen) {
      if (item) {
        const type = item.product_id ? 'product' : 'bundle'
        setItemType(type)
        reset({
          item_type: type,
          product_id: item.product_id,
          bundle_id: item.bundle_id,
          quantity: item.quantity,
          unit_price: Number(item.unit_price),
          cleaning_fee: Number(item.cleaning_fee),
          tax_rate: Number(item.tax_rate),
          notes: item.notes || '',
        })
      } else {
        reset({
          item_type: 'product',
          quantity: 1,
          unit_price: 0,
          cleaning_fee: 0,
          tax_rate: 20,
        })
        setItemType('product')
      }
    }
  }, [isOpen, item, reset])

  const addMutation = useMutation({
    mutationFn: (data: any) => eventsApi.addItem(eventId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event', eventId] })
      queryClient.invalidateQueries({ queryKey: ['events'] })
      onClose()
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: any) => eventsApi.updateItem(item!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event', eventId] })
      queryClient.invalidateQueries({ queryKey: ['events'] })
      onClose()
    },
  })

  const onSubmit = (data: FormData) => {
    const itemData = {
      product_id: data.item_type === 'product' ? data.product_id : undefined,
      bundle_id: data.item_type === 'bundle' ? data.bundle_id : undefined,
      quantity: data.quantity,
      unit_price: data.unit_price,
      cleaning_fee: data.cleaning_fee || 0,
      tax_rate: data.tax_rate,
      notes: data.notes || undefined,
    }

    if (isEdit) {
      updateMutation.mutate(itemData)
    } else {
      addMutation.mutate(itemData)
    }
  }

  const isLoading = addMutation.isPending || updateMutation.isPending
  const error = addMutation.error || updateMutation.error

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier l\'article' : 'Ajouter un article'}
      size="md"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={handleSubmit(onSubmit)}
          cancelText="Annuler"
          confirmText={isEdit ? 'Enregistrer' : 'Ajouter'}
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

        {/* Type d'article */}
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-2">
            Type d'article
          </label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                value="product"
                checked={itemType === 'product'}
                onChange={(e) => {
                  setItemType('product')
                  setValue('item_type', 'product')
                  setValue('bundle_id', undefined)
                }}
                className="w-4 h-4 text-primary-600"
              />
              <span className="text-sm">Produit</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                value="bundle"
                checked={itemType === 'bundle'}
                onChange={(e) => {
                  setItemType('bundle')
                  setValue('item_type', 'bundle')
                  setValue('product_id', undefined)
                }}
                className="w-4 h-4 text-primary-600"
              />
              <span className="text-sm">Formule</span>
            </label>
          </div>
        </div>

        {/* Sélection produit ou bundle */}
        {itemType === 'product' ? (
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Produit *
            </label>
            <select
              {...register('product_id', { valueAsNumber: true })}
              className="input w-full"
            >
              <option value="">Sélectionner un produit</option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name} - {Number(product.base_price).toFixed(2)} €
                </option>
              ))}
            </select>
            {errors.product_id && (
              <p className="text-red-500 text-sm mt-1">{errors.product_id.message}</p>
            )}
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Formule *
            </label>
            <select
              {...register('bundle_id', { valueAsNumber: true })}
              className="input w-full"
            >
              <option value="">Sélectionner une formule</option>
              {bundles.map((bundle) => (
                <option key={bundle.id} value={bundle.id}>
                  {bundle.name} - {Number(bundle.bundle_price).toFixed(2)} €
                </option>
              ))}
            </select>
            {errors.bundle_id && (
              <p className="text-red-500 text-sm mt-1">{errors.bundle_id.message}</p>
            )}
          </div>
        )}

        {/* Quantité */}
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Quantité *
          </label>
          <input
            {...register('quantity', { valueAsNumber: true })}
            type="number"
            min="1"
            className="input w-full"
          />
          {errors.quantity && (
            <p className="text-red-500 text-sm mt-1">{errors.quantity.message}</p>
          )}
        </div>

        {/* Prix et frais */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Prix unitaire (€) *
            </label>
            <input
              {...register('unit_price', { valueAsNumber: true })}
              type="number"
              step="0.01"
              className="input w-full"
            />
            {errors.unit_price && (
              <p className="text-red-500 text-sm mt-1">{errors.unit_price.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Frais nettoyage (€)
            </label>
            <input
              {...register('cleaning_fee', { valueAsNumber: true })}
              type="number"
              step="0.01"
              className="input w-full"
            />
            {errors.cleaning_fee && (
              <p className="text-red-500 text-sm mt-1">{errors.cleaning_fee.message}</p>
            )}
          </div>
        </div>

        {/* TVA */}
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Taux de TVA (%) *
          </label>
          <input
            {...register('tax_rate', { valueAsNumber: true })}
            type="number"
            step="0.01"
            min="0"
            max="100"
            className="input w-full"
          />
          {errors.tax_rate && (
            <p className="text-red-500 text-sm mt-1">{errors.tax_rate.message}</p>
          )}
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Notes
          </label>
          <textarea
            {...register('notes')}
            className="input w-full"
            rows={3}
            placeholder="Notes optionnelles..."
          />
        </div>

        {/* Calcul total */}
        <div className="border-t border-dark-700 pt-4 space-y-2">
          <div className="flex justify-between text-sm text-dark-300">
            <span>Sous-total ({watch('quantity') || 1} × {Number(watch('unit_price') || 0).toFixed(2)} €)</span>
            <span>{(Number(watch('unit_price') || 0) * Number(watch('quantity') || 1)).toFixed(2)} €</span>
          </div>
          {(watch('cleaning_fee') || 0) > 0 && (
            <div className="flex justify-between text-sm text-dark-300">
              <span>Frais de nettoyage</span>
              <span>{Number(watch('cleaning_fee') || 0).toFixed(2)} €</span>
            </div>
          )}
          <div className="flex justify-between items-center font-semibold border-t border-dark-700 pt-2">
            <span>Total HT</span>
            <span>
              {(() => {
                const totalHT = (Number(watch('unit_price') || 0) * Number(watch('quantity') || 1)) + Number(watch('cleaning_fee') || 0)
                return totalHT.toFixed(2)
              })()} €
            </span>
          </div>
          <div className="flex justify-between text-sm text-dark-300">
            <span>TVA ({Number(watch('tax_rate') || 20).toFixed(2)}%)</span>
            <span>
              {(() => {
                const totalHT = (Number(watch('unit_price') || 0) * Number(watch('quantity') || 1)) + Number(watch('cleaning_fee') || 0)
                const tva = totalHT * (Number(watch('tax_rate') || 20) / 100)
                return tva.toFixed(2)
              })()} €
            </span>
          </div>
          <div className="flex justify-between items-center text-lg font-bold border-t border-dark-700 pt-2">
            <span>Total TTC</span>
            <span className="text-green-500">
              {(() => {
                const totalHT = (Number(watch('unit_price') || 0) * Number(watch('quantity') || 1)) + Number(watch('cleaning_fee') || 0)
                const totalTTC = totalHT * (1 + Number(watch('tax_rate') || 20) / 100)
                return totalTTC.toFixed(2)
              })()} €
            </span>
          </div>
        </div>
      </form>
    </Modal>
  )
}
