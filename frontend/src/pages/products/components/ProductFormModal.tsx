import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import { productsApi } from '@/api/products'
import { categoriesApi } from '@/api/categories'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { Product, ProductCreate, ProductUpdate } from '@/types/product'

// Validation schemas
const createProductSchema = z.object({
  category_id: z.number().optional().nullable(),
  sku: z.string().min(1, 'SKU requis'),
  name: z.string().min(1, 'Nom requis'),
  description: z.string().optional(),
  short_description: z.string().optional(),
  stock_quantity: z.number().min(0, 'Stock invalide').default(0),
  base_price: z.number().min(0, 'Prix invalide'),
  featured: z.boolean().default(false),
  is_active: z.boolean().default(true),
})

const updateProductSchema = z.object({
  category_id: z.number().optional().nullable(),
  sku: z.string().min(1, 'SKU requis').optional(),
  name: z.string().min(1, 'Nom requis').optional(),
  description: z.string().optional(),
  short_description: z.string().optional(),
  stock_quantity: z.number().min(0, 'Stock invalide').optional(),
  base_price: z.number().min(0, 'Prix invalide').optional(),
  featured: z.boolean().optional(),
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
      category_id: null,
      sku: '',
      name: '',
      description: '',
      short_description: '',
      stock_quantity: 0,
      base_price: 0,
      featured: false,
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
          category_id: product.category_id,
          sku: product.sku,
          name: product.name,
          description: product.description || '',
          short_description: product.short_description || '',
          stock_quantity: product.stock_quantity,
          base_price: product.base_price,
          featured: product.featured,
          is_active: product.is_active,
        })
      } else {
        reset({
          category_id: null,
          sku: '',
          name: '',
          description: '',
          short_description: '',
          stock_quantity: 0,
          base_price: 0,
          featured: false,
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

  const onSubmit = (data: CreateFormData | UpdateFormData) => {
    if (isEdit && product) {
      updateMutation.mutate({ id: product.id, data: data as ProductUpdate })
    } else {
      createMutation.mutate(data as ProductCreate)
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <Modal
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
            {...register('category_id', {
              setValueAs: (v) => (v === '' ? null : Number(v)),
            })}
            className="input w-full"
          >
            <option value="">Aucune catégorie</option>
            {categories?.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Description courte
          </label>
          <input
            {...register('short_description')}
            type="text"
            className="input w-full"
            placeholder="Une ligne de description"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Description complète
          </label>
          <textarea
            {...register('description')}
            className="input w-full"
            rows={4}
            placeholder="Description détaillée du produit..."
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Prix de base (€) *
            </label>
            <input
              {...register('base_price', { valueAsNumber: true })}
              type="number"
              step="0.01"
              className="input w-full"
              placeholder="0.00"
            />
            {errors.base_price && (
              <p className="text-red-500 text-sm mt-1">
                {errors.base_price.message}
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

        <div className="flex items-center gap-6">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              {...register('featured')}
              type="checkbox"
              className="w-4 h-4 rounded border-dark-600 bg-dark-700 text-primary-600 focus:ring-primary-600"
            />
            <span className="text-sm text-dark-300">Produit en vedette</span>
          </label>

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
    </Modal>
  )
}
