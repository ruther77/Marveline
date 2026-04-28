import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useCategoriesList, useCreateProduct, useUpdateProduct } from '@/api/queries'
import { BottomSheet } from '@shared/components/ui/BottomSheet'
import { ModalFooter } from '@shared/components/ui/Modal'
import type { Product, ProductCreate, ProductUpdate } from '@/types/product'
import { ProductImageGallery } from './ProductImageGallery'
import { normalizeError } from '@shared/errors/normalizer'

// Validation schemas — prix en euros dans le form, conversion centimes au submit
const TVA_OPTIONS = [
  { label: '0 %', value: 0 },
  { label: '5,5 %', value: 0.055 },
  { label: '10 %', value: 0.10 },
  { label: '20 %', value: 0.20 },
]

const createProductSchema = z.object({
  category: z.string().min(1, 'Catégorie requise'),
  sku: z.string().min(1, 'SKU requis'),
  name: z.string().min(1, 'Nom requis'),
  stock_quantity: z.number().min(0, 'Stock invalide').default(0),
  price_per_day_euros: z.number().min(0, 'Prix invalide'),
  tva_rate: z.number().min(0).max(1).default(0.20),
  condition: z.string().optional().default('bon'),
  is_active: z.boolean().default(true),
  weight_grams: z.number().min(0).nullable().optional(),
  volume_cm3: z.number().min(0).nullable().optional(),
})

const updateProductSchema = z.object({
  category: z.string().optional(),
  sku: z.string().min(1, 'SKU requis').optional(),
  name: z.string().min(1, 'Nom requis').optional(),
  stock_quantity: z.number().min(0, 'Stock invalide').optional(),
  price_per_day_euros: z.number().min(0, 'Prix invalide').optional(),
  tva_rate: z.number().min(0).max(1).optional(),
  condition: z.string().optional(),
  is_active: z.boolean().optional(),
  weight_grams: z.number().min(0).nullable().optional(),
  volume_cm3: z.number().min(0).nullable().optional(),
})

type CreateFormData = z.infer<typeof createProductSchema>
type UpdateFormData = z.infer<typeof updateProductSchema>

interface ProductFormModalProps {
  isOpen: boolean
  onClose: () => void
  product?: Product | null
  mode: 'create' | 'edit'
}

export function ProductFormModal({
  isOpen,
  onClose,
  product,
  mode,
}: ProductFormModalProps) {
  const isEdit = mode === 'edit'

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateFormData | UpdateFormData>({
    resolver: zodResolver(isEdit ? updateProductSchema : createProductSchema),
    defaultValues: {
      category: '',
      sku: '',
      name: '',
      stock_quantity: 0,
      price_per_day_euros: 0,
      tva_rate: 0.20,
      condition: 'bon',
      is_active: true,
    },
  })

  const { data: categories } = useCategoriesList(true)

  // Reset form when product changes or modal opens
  useEffect(() => {
    if (isOpen) {
      if (product) {
        reset({
          category: product.category || '',
          sku: product.sku,
          name: product.name,
          stock_quantity: product.stock_quantity,
          price_per_day_euros: product.price_per_day_euros,
          tva_rate: product.tva_rate ?? 0.20,
          condition: product.condition || 'good',
          is_active: product.is_active,
          weight_grams: product.weight_grams ?? null,
          volume_cm3: product.volume_cm3 ?? null,
        })
      } else {
        reset({
          category: '',
          sku: '',
          name: '',
          stock_quantity: 0,
          price_per_day_euros: 0,
          tva_rate: 0.20,
          condition: 'bon',
          is_active: true,
          weight_grams: null,
          volume_cm3: null,
        })
      }
    }
  }, [isOpen, product, reset])

  const createMutation = useCreateProduct()
  const updateMutation = useUpdateProduct()

  const onSubmit = (formData: CreateFormData | UpdateFormData) => {
    // Convertir euros → centimes pour le backend
    const { price_per_day_euros, ...rest } = formData
    const backendData = {
      ...rest,
      // category vide = ne pas envoyer (evite 422 sur enum vide)
      category: formData.category && formData.category !== '' ? formData.category : undefined,
      price_per_day_cents: price_per_day_euros !== undefined
        ? Math.round(price_per_day_euros * 100)
        : undefined,
      tva_rate: formData.tva_rate,
      // Supprimer price_per_day_euros du payload backend
    }
    delete (backendData as Record<string, unknown>).price_per_day_euros

    if (isEdit && product) {
      updateMutation.mutate({ id: product.id, data: backendData as ProductUpdate }, { onSuccess: onClose })
    } else {
      createMutation.mutate(backendData as unknown as ProductCreate, { onSuccess: onClose })
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <BottomSheet
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier le produit' : 'Nouveau produit'}
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

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="name" className="block text-sm text-dark-400 mb-1">
              Nom du produit *
            </label>
            <input
              id="name"
              {...register('name')}
              type="text"
              className="input"
              placeholder="Chaise Napoleon III"
            />
            {errors.name && (
              <p className="text-red-500 text-sm mt-1">{errors.name.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="sku" className="block text-sm text-dark-400 mb-1">
              SKU *
            </label>
            <input
              id="sku"
              {...register('sku')}
              type="text"
              className="input"
              placeholder="CHR-NAP-001"
            />
            {errors.sku && (
              <p className="text-red-500 text-sm mt-1">{errors.sku.message}</p>
            )}
          </div>
        </div>

        <div>
          <label htmlFor="category" className="block text-sm text-dark-400 mb-1">
            Catégorie
          </label>
          <select
            id="category"
            {...register('category')}
            className="input"
          >
            <option value="">Aucune catégorie</option>
            {categories?.map((cat) => (
              <option key={cat.id} value={cat.slug}>
                {cat.name}
              </option>
            ))}
          </select>
          {errors.category && (
            <p className="text-red-500 text-sm mt-1">{errors.category.message}</p>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="price_per_day_euros" className="block text-sm text-dark-400 mb-1">
              Prix par jour (€) *
            </label>
            <input
              id="price_per_day_euros"
              {...register('price_per_day_euros', { valueAsNumber: true })}
              type="number"
              step="0.01"
              className="input"
              placeholder="0.00"
            />
            {errors.price_per_day_euros && (
              <p className="text-red-500 text-sm mt-1">
                {errors.price_per_day_euros.message}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="stock_quantity" className="block text-sm text-dark-400 mb-1">
              Stock initial
            </label>
            <input
              id="stock_quantity"
              {...register('stock_quantity', { valueAsNumber: true })}
              type="number"
              className="input"
              placeholder="0"
            />
            {errors.stock_quantity && (
              <p className="text-red-500 text-sm mt-1">
                {errors.stock_quantity.message}
              </p>
            )}
          </div>
        </div>

        <div>
          <label htmlFor="tva_rate" className="block text-sm text-dark-400 mb-1">
            Taux TVA
          </label>
          <select
            id="tva_rate"
            {...register('tva_rate', { valueAsNumber: true })}
            className="input"
          >
            {TVA_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="condition" className="block text-sm text-dark-400 mb-1">
            État
          </label>
          <select
            id="condition"
            {...register('condition')}
            className="input"
          >
            <option value="neuf">Neuf</option>
            <option value="bon">Bon état</option>
            <option value="use">Usé</option>
            <option value="hors_service">Hors service</option>
          </select>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="weight_grams" className="block text-sm text-dark-400 mb-1">
              Poids (grammes)
            </label>
            <input
              id="weight_grams"
              {...register('weight_grams', { valueAsNumber: true, setValueAs: (v) => v === '' || v === null ? null : Number(v) })}
              type="number"
              min="0"
              className="input"
              placeholder="ex: 350"
            />
          </div>

          <div>
            <label htmlFor="volume_cm3" className="block text-sm text-dark-400 mb-1">
              Volume (cm³)
            </label>
            <input
              id="volume_cm3"
              {...register('volume_cm3', { valueAsNumber: true, setValueAs: (v) => v === '' || v === null ? null : Number(v) })}
              type="number"
              min="0"
              className="input"
              placeholder="ex: 1200"
            />
          </div>
        </div>

        <div className="flex items-center gap-6">
          <label htmlFor="is_active" className="flex items-center gap-2 cursor-pointer">
            <input
              id="is_active"
              {...register('is_active')}
              type="checkbox"
              className="w-4 h-4 rounded border-dark-600 bg-dark-900 text-primary-600 focus:ring-primary-600"
            />
            <span className="text-sm text-dark-300">Produit actif</span>
          </label>
        </div>

        {isEdit && product && (
          <ProductImageGallery productId={product.id} />
        )}
      </form>
    </BottomSheet>
  )
}
