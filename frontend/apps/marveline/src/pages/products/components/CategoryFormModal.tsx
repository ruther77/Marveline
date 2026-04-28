import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useCategoriesList, useCreateCategory, useUpdateCategory } from '@/api/queries'
import { BottomSheet } from '@shared/components/ui/BottomSheet'
import { ModalFooter } from '@shared/components/ui/Modal'
import type { Category, CategoryCreate, CategoryUpdate } from '@/types/product'
import { normalizeError } from '@shared/errors/normalizer'

const createCategorySchema = z.object({
  name: z.string().min(1, 'Nom requis'),
  parent_id: z.number().optional().nullable(),
  description: z.string().optional(),
  image_url: z.string().url('URL invalide').optional().or(z.literal('')),
  display_order: z.number().min(0).default(0),
  is_active: z.boolean().default(true),
})

const updateCategorySchema = z.object({
  name: z.string().min(1, 'Nom requis').optional(),
  parent_id: z.number().optional().nullable(),
  description: z.string().optional(),
  image_url: z.string().url('URL invalide').optional().or(z.literal('')),
  display_order: z.number().min(0).optional(),
  is_active: z.boolean().optional(),
})

type CreateFormData = z.infer<typeof createCategorySchema>
type UpdateFormData = z.infer<typeof updateCategorySchema>

interface CategoryFormModalProps {
  isOpen: boolean
  onClose: () => void
  category?: Category | null
  mode: 'create' | 'edit'
}

export function CategoryFormModal({
  isOpen,
  onClose,
  category,
  mode,
}: CategoryFormModalProps) {
  const isEdit = mode === 'edit'

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateFormData | UpdateFormData>({
    resolver: zodResolver(isEdit ? updateCategorySchema : createCategorySchema),
    defaultValues: {
      name: '',
      parent_id: null,
      description: '',
      image_url: '',
      display_order: 0,
      is_active: true,
    },
  })

  const { data: categories } = useCategoriesList(false)

  // Filter out current category and its descendants to prevent circular refs
  const availableParents = categories?.filter((c) => {
    if (!category) return true
    return c.id !== category.id && c.parent_id !== category.id
  })

  useEffect(() => {
    if (isOpen) {
      if (category) {
        reset({
          name: category.name,
          parent_id: category.parent_id,
          description: category.description || '',
          image_url: category.image_url || '',
          display_order: category.display_order,
          is_active: category.is_active,
        })
      } else {
        reset({
          name: '',
          parent_id: null,
          description: '',
          image_url: '',
          display_order: 0,
          is_active: true,
        })
      }
    }
  }, [isOpen, category, reset])

  const createMutation = useCreateCategory()
  const updateMutation = useUpdateCategory()

  const onSubmit = (data: CreateFormData | UpdateFormData) => {
    // Clean empty strings
    const cleanData = {
      ...data,
      image_url: data.image_url || undefined,
      description: data.description || undefined,
    }

    if (isEdit && category) {
      updateMutation.mutate({ id: category.id, data: cleanData as CategoryUpdate }, { onSuccess: onClose })
    } else {
      createMutation.mutate(cleanData as CategoryCreate, { onSuccess: onClose })
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <BottomSheet
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier la catégorie' : 'Nouvelle catégorie'}
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
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {normalizeError(error).message || 'Une erreur est survenue'}
          </div>
        )}

        <div>
          <label htmlFor="category-name" className="block text-sm text-dark-400 mb-1">
            Nom de la catégorie *
          </label>
          <input
            id="category-name"
            {...register('name')}
            type="text"
            className="input"
            placeholder="Mobilier"
          />
          {errors.name && (
            <p className="text-red-500 text-sm mt-1">{errors.name.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="category-parent" className="block text-sm text-dark-400 mb-1">
            Catégorie parente
          </label>
          <select
            id="category-parent"
            {...register('parent_id', {
              setValueAs: (v) => (v === '' ? null : Number(v)),
            })}
            className="input"
          >
            <option value="">Aucune (catégorie racine)</option>
            {availableParents?.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="category-description" className="block text-sm text-dark-400 mb-1">
            Description
          </label>
          <textarea
            id="category-description"
            {...register('description')}
            className="input"
            rows={3}
            placeholder="Description de la catégorie..."
          />
        </div>

        <div>
          <label htmlFor="category-image-url" className="block text-sm text-dark-400 mb-1">
            URL de l'image
          </label>
          <input
            id="category-image-url"
            {...register('image_url')}
            type="text"
            className="input"
            placeholder="https://example.com/image.jpg"
          />
          {errors.image_url && (
            <p className="text-red-500 text-sm mt-1">
              {errors.image_url.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="category-display-order" className="block text-sm text-dark-400 mb-1">
            Ordre d'affichage
          </label>
          <input
            id="category-display-order"
            {...register('display_order', { valueAsNumber: true })}
            type="number"
            className="input"
            placeholder="0"
          />
          <p className="text-xs text-dark-400 mt-1">
            Les categories avec un ordre plus petit apparaissent en premier
          </p>
        </div>

        <div>
          <label htmlFor="category-is-active" className="flex items-center gap-2 cursor-pointer">
            <input
              id="category-is-active"
              {...register('is_active')}
              type="checkbox"
              className="w-4 h-4 rounded border-dark-600 bg-dark-900 text-primary-600 focus:ring-primary-600"
            />
            <span className="text-sm text-dark-300">Catégorie active</span>
          </label>
        </div>
      </form>
    </BottomSheet>
  )
}
