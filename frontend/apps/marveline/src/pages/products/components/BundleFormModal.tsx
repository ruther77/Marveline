import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useCreateBundle, useUpdateBundle } from '@/api/queries'
import { BottomSheet } from '@shared/components/ui/BottomSheet'
import { ModalFooter } from '@shared/components/ui/Modal'
import type { Bundle, BundleCreate, BundleUpdate } from '@/types/product'
import { normalizeError } from '@shared/errors/normalizer'

const createBundleSchema = z.object({
  name: z.string().min(1, 'Nom requis'),
  description: z.string().optional(),
  image_url: z.string().url('URL invalide').optional().or(z.literal('')),
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
  image_url: z.string().url('URL invalide').optional().or(z.literal('')),
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
      image_url: '',
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
          image_url: bundle.image_url || '',
          bundle_price: bundle.bundle_price_cents / 100, // Centimes → euros
          cleaning_fee: bundle.cleaning_fee_cents / 100, // Centimes → euros
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

  const createMutation = useCreateBundle()
  const updateMutation = useUpdateBundle()

  const onSubmit = (data: CreateFormData | UpdateFormData) => {
    // Convertir euros → centimes et utiliser les noms de champs corrects pour le backend
    const { bundle_price, cleaning_fee, ...rest } = data
    const backendData = {
      ...rest,
      description: data.description || undefined,
      image_url: data.image_url || undefined,
      bundle_price_cents: bundle_price !== undefined ? Math.round(bundle_price * 100) : undefined,
      cleaning_fee_cents: cleaning_fee !== undefined ? Math.round(cleaning_fee * 100) : undefined,
    }

    if (isEdit && bundle) {
      updateMutation.mutate({ id: bundle.id, data: backendData as BundleUpdate }, { onSuccess: onClose })
    } else {
      createMutation.mutate(backendData as BundleCreate, { onSuccess: onClose })
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
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {normalizeError(error).message || 'Une erreur est survenue'}
          </div>
        )}

        <div>
          <label htmlFor="bundle-name" className="block text-sm text-dark-400 mb-1">
            Nom de la formule *
          </label>
          <input
            id="bundle-name"
            {...register('name')}
            type="text"
            className="input"
            placeholder="Pack Mariage Complet"
          />
          {errors.name && (
            <p className="text-red-500 text-sm mt-1">{errors.name.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="bundle-description" className="block text-sm text-dark-400 mb-1">
            Description
          </label>
          <textarea
            id="bundle-description"
            {...register('description')}
            className="input"
            rows={3}
            placeholder="Description de la formule..."
          />
        </div>

        <div>
          <label htmlFor="bundle-image-url" className="block text-sm text-dark-400 mb-1">
            Image URL
          </label>
          <input
            id="bundle-image-url"
            {...register('image_url')}
            className="input"
            placeholder="https://..."
          />
          {errors.image_url && (
            <p className="text-red-500 text-sm mt-1">{errors.image_url.message}</p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="bundle-price" className="block text-sm text-dark-400 mb-1">
              Prix formule (€)
            </label>
            <input
              id="bundle-price"
              {...register('bundle_price', { valueAsNumber: true })}
              type="number"
              step="0.01"
              className="input"
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
            <label htmlFor="bundle-cleaning-fee" className="block text-sm text-dark-400 mb-1">
              Frais de nettoyage (€)
            </label>
            <input
              id="bundle-cleaning-fee"
              {...register('cleaning_fee', { valueAsNumber: true })}
              type="number"
              step="0.01"
              min="0"
              className="input"
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
          <label htmlFor="bundle-featured" className="flex items-center gap-2 cursor-pointer">
            <input
              id="bundle-featured"
              {...register('featured')}
              type="checkbox"
              className="w-4 h-4 rounded border-dark-600 bg-dark-900 text-primary-600 focus:ring-primary-600"
            />
            <span className="text-sm text-dark-300">Formule en vedette</span>
          </label>

          <label htmlFor="bundle-is-active" className="flex items-center gap-2 cursor-pointer">
            <input
              id="bundle-is-active"
              {...register('is_active')}
              type="checkbox"
              className="w-4 h-4 rounded border-dark-600 bg-dark-900 text-primary-600 focus:ring-primary-600"
            />
            <span className="text-sm text-dark-300">Formule active</span>
          </label>
        </div>

        {isEdit && bundle && (
          <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-400 text-sm">
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
