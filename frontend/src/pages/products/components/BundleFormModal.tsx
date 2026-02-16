import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { bundlesApi } from '@/api/bundles'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { ModalFooter } from '@/components/ui/Modal'
import type { Bundle, BundleCreate, BundleUpdate } from '@/types/product'

const createBundleSchema = z.object({
  name: z.string().min(1, 'Nom requis'),
  description: z.string().optional(),
  bundle_price: z.number().min(0, 'Prix invalide').default(0),
  cleaning_fee: z
    .number()
    .min(0, 'Frais invalide')
    .default(0),
  featured: z.boolean().default(false),
  is_active: z.boolean().default(true),
})

const updateBundleSchema = z.object({
  name: z.string().min(1, 'Nom requis').optional(),
  description: z.string().optional(),
  bundle_price: z.number().min(0, 'Prix invalide').optional(),
  cleaning_fee: z
    .number()
    .min(0, 'Frais invalide')
    .optional(),
  featured: z.boolean().optional(),
  is_active: z.boolean().optional(),
})

type CreateFormData = z.infer<typeof createBundleSchema>
type UpdateFormData = z.infer<typeof updateBundleSchema>

interface BundleFormModalProps {
  isOpen: boolean
  onClose: () => void
  bundle?: Bundle | null
  mode: 'create' | 'edit'
}

export function BundleFormModal({
  isOpen,
  onClose,
  bundle,
  mode,
}: BundleFormModalProps) {
  const queryClient = useQueryClient()
  const isEdit = mode === 'edit'

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateFormData | UpdateFormData>({
    resolver: zodResolver(isEdit ? updateBundleSchema : createBundleSchema),
    defaultValues: {
      name: '',
      description: '',
      bundle_price: 0,
      cleaning_fee: 0,
      featured: false,
      is_active: true,
    },
  })

  useEffect(() => {
    if (isOpen) {
      if (bundle) {
        reset({
          name: bundle.name,
          description: bundle.description || '',
          bundle_price: bundle.bundle_price / 100, // Centimes → euros
          cleaning_fee: bundle.cleaning_fee / 100, // Centimes → euros
          featured: bundle.featured,
          is_active: bundle.is_active,
        })
      } else {
        reset({
          name: '',
          description: '',
          bundle_price: 0,
          cleaning_fee: 0,
          featured: false,
          is_active: true,
        })
      }
    }
  }, [isOpen, bundle, reset])

  const createMutation = useMutation({
    mutationFn: (data: BundleCreate) => bundlesApi.createBundle(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bundles'] })
      onClose()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: BundleUpdate }) =>
      bundlesApi.updateBundle(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bundles'] })
      onClose()
    },
  })

  const onSubmit = (data: CreateFormData | UpdateFormData) => {
    // Convertir euros → centimes et utiliser les noms de champs corrects pour le backend
    const { bundle_price, cleaning_fee, ...rest } = data
    const backendData = {
      ...rest,
      description: data.description || undefined,
      bundle_price_cents: bundle_price !== undefined ? Math.round(bundle_price * 100) : undefined,
      cleaning_fee_cents: cleaning_fee !== undefined ? Math.round(cleaning_fee * 100) : undefined,
    }

    if (isEdit && bundle) {
      updateMutation.mutate({ id: bundle.id, data: backendData as BundleUpdate })
    } else {
      createMutation.mutate(backendData as BundleCreate)
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <BottomSheet
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier la formule' : 'Nouvelle formule'}
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
            Nom de la formule *
          </label>
          <input
            {...register('name')}
            type="text"
            className="input w-full"
            placeholder="Pack Mariage Complet"
          />
          {errors.name && (
            <p className="text-red-500 text-sm mt-1">{errors.name.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Description
          </label>
          <textarea
            {...register('description')}
            className="input w-full"
            rows={3}
            placeholder="Description de la formule..."
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Prix formule (€)
            </label>
            <input
              {...register('bundle_price', { valueAsNumber: true })}
              type="number"
              step="0.01"
              className="input w-full"
              placeholder="0.00"
            />
            {errors.bundle_price && (
              <p className="text-red-500 text-sm mt-1">
                {errors.bundle_price.message}
              </p>
            )}
            <p className="text-xs text-dark-400 mt-1">
              Prix total de la formule
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Frais de nettoyage (€)
            </label>
            <input
              {...register('cleaning_fee', { valueAsNumber: true })}
              type="number"
              step="0.01"
              min="0"
              className="input w-full"
              placeholder="0.00"
            />
            {errors.cleaning_fee && (
              <p className="text-red-500 text-sm mt-1">
                {errors.cleaning_fee.message}
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
            <span className="text-sm text-dark-300">Formule en vedette</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              {...register('is_active')}
              type="checkbox"
              className="w-4 h-4 rounded border-dark-600 bg-dark-700 text-primary-600 focus:ring-primary-600"
            />
            <span className="text-sm text-dark-300">Formule active</span>
          </label>
        </div>

        {isEdit && bundle && (
          <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-400 text-sm">
            <p className="font-medium">Note :</p>
            <p className="mt-1">
              Utilisez la page de détails pour gérer les produits inclus dans
              cette formule.
            </p>
          </div>
        )}
      </form>
    </BottomSheet>
  )
}
