import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import { categoriesApi } from '@/api/categories'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { Category, CategoryCreate, CategoryUpdate } from '@/types/product'

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
  const queryClient = useQueryClient()
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

  const { data: categories } = useQuery({
    queryKey: ['categories', false],
    queryFn: () => categoriesApi.getCategories(false),
    enabled: isOpen,
  })

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

  const createMutation = useMutation({
    mutationFn: (data: CategoryCreate) => categoriesApi.createCategory(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      onClose()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: CategoryUpdate }) =>
      categoriesApi.updateCategory(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      onClose()
    },
  })

  const onSubmit = (data: CreateFormData | UpdateFormData) => {
    // Clean empty strings
    const cleanData = {
      ...data,
      image_url: data.image_url || undefined,
      description: data.description || undefined,
    }

    if (isEdit && category) {
      updateMutation.mutate({
        id: category.id,
        data: cleanData as CategoryUpdate,
      })
    } else {
      createMutation.mutate(cleanData as CategoryCreate)
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <Modal
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
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {(error as Error).message || 'Une erreur est survenue'}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Nom de la catégorie *
          </label>
          <input
            {...register('name')}
            type="text"
            className="input w-full"
            placeholder="Mobilier"
          />
          {errors.name && (
            <p className="text-red-500 text-sm mt-1">{errors.name.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Catégorie parente
          </label>
          <select
            {...register('parent_id', {
              setValueAs: (v) => (v === '' ? null : Number(v)),
            })}
            className="input w-full"
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
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Description
          </label>
          <textarea
            {...register('description')}
            className="input w-full"
            rows={3}
            placeholder="Description de la catégorie..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            URL de l'image
          </label>
          <input
            {...register('image_url')}
            type="text"
            className="input w-full"
            placeholder="https://example.com/image.jpg"
          />
          {errors.image_url && (
            <p className="text-red-500 text-sm mt-1">
              {errors.image_url.message}
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Ordre d'affichage
          </label>
          <input
            {...register('display_order', { valueAsNumber: true })}
            type="number"
            className="input w-full"
            placeholder="0"
          />
          <p className="text-xs text-dark-400 mt-1">
            Les catégories avec un ordre plus petit apparaissent en premier
          </p>
        </div>

        <div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              {...register('is_active')}
              type="checkbox"
              className="w-4 h-4 rounded border-dark-600 bg-dark-700 text-primary-600 focus:ring-primary-600"
            />
            <span className="text-sm text-dark-300">Catégorie active</span>
          </label>
        </div>
      </form>
    </Modal>
  )
}
