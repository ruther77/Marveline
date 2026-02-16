import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import { productsApi } from '@/api/products'
import { categoriesApi } from '@/api/categories'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { ModalFooter } from '@/components/ui/Modal'
import type { Product, ProductCreate, ProductUpdate } from '@/types/product'

// Validation schemas — prix en euros dans le form, conversion centimes au submit
const createProductSchema = z.object({
  category: z.string().optional().default(''),
  sku: z.string().min(1, 'SKU requis'),
  name: z.string().min(1, 'Nom requis'),
  stock_quantity: z.number().min(0, 'Stock invalide').default(0),
  price_per_day_euros: z.number().min(0, 'Prix invalide'),
  condition: z.string().optional().default('good'),
  is_active: z.boolean().default(true),
})

const updateProductSchema = z.object({
  category: z.string().optional(),
  sku: z.string().min(1, 'SKU requis').optional(),
  name: z.string().min(1, 'Nom requis').optional(),
  stock_quantity: z.number().min(0, 'Stock invalide').optional(),
  price_per_day_euros: z.number().min(0, 'Prix invalide').optional(),
  condition: z.string().optional(),
  is_active: z.boolean().optional(),
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
  const queryClient = useQueryClient()
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
      condition: 'good',
      is_active: true,
    },
  })

  const { data: categories } = useQuery({
    queryKey: ['categories'],
    queryFn: () => categoriesApi.getCategories(true),
    enabled: isOpen,
  })

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
          condition: product.condition || 'good',
          is_active: product.is_active,
        })
      } else {
        reset({
          category: '',
          sku: '',
          name: '',
          stock_quantity: 0,
          price_per_day_euros: 0,
          condition: 'good',
          is_active: true,
        })
      }
    }
  }, [isOpen, product, reset])

  const createMutation = useMutation({
    mutationFn: (data: ProductCreate) => productsApi.createProduct(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      onClose()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProductUpdate }) =>
      productsApi.updateProduct(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      onClose()
    },
  })

  const onSubmit = (formData: CreateFormData | UpdateFormData) => {
    // Convertir euros → centimes pour le backend
    const { price_per_day_euros, ...rest } = formData
    const backendData = {
      ...rest,
      category: formData.category || undefined,
      price_per_day_cents: price_per_day_euros !== undefined
        ? Math.round(price_per_day_euros * 100)
        : undefined,
    }

    if (isEdit && product) {
      updateMutation.mutate({ id: product.id, data: backendData as ProductUpdate })
    } else {
      createMutation.mutate(backendData as unknown as ProductCreate)
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
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {(error as Error).message || 'Une erreur est survenue'}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Nom du produit *
            </label>
            <input
              {...register('name')}
              type="text"
              className="input w-full"
              placeholder="Chaise Napoleon III"
            />
            {errors.name && (
              <p className="text-red-500 text-sm mt-1">{errors.name.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              SKU *
            </label>
            <input
              {...register('sku')}
              type="text"
              className="input w-full"
              placeholder="CHR-NAP-001"
            />
            {errors.sku && (
              <p className="text-red-500 text-sm mt-1">{errors.sku.message}</p>
            )}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Catégorie
          </label>
          <select
            {...register('category')}
            className="input w-full"
          >
            <option value="">Aucune catégorie</option>
            {categories?.map((cat) => (
              <option key={cat.id} value={cat.slug}>
                {cat.name}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Prix par jour (€) *
            </label>
            <input
              {...register('price_per_day_euros', { valueAsNumber: true })}
              type="number"
              step="0.01"
              className="input w-full"
              placeholder="0.00"
            />
            {errors.price_per_day_euros && (
              <p className="text-red-500 text-sm mt-1">
                {errors.price_per_day_euros.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Stock initial
            </label>
            <input
              {...register('stock_quantity', { valueAsNumber: true })}
              type="number"
              className="input w-full"
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
          <label className="block text-sm font-medium text-dark-300 mb-1">
            État
          </label>
          <select
            {...register('condition')}
            className="input w-full"
          >
            <option value="new">Neuf</option>
            <option value="good">Bon état</option>
            <option value="fair">Correct</option>
            <option value="poor">Usé</option>
          </select>
        </div>

        <div className="flex items-center gap-6">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              {...register('is_active')}
              type="checkbox"
              className="w-4 h-4 rounded border-dark-600 bg-dark-700 text-primary-600 focus:ring-primary-600"
            />
            <span className="text-sm text-dark-300">Produit actif</span>
          </label>
        </div>
      </form>
    </BottomSheet>
  )
}
