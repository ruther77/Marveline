import { useEffect, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useCreateProductVariant, useUpdateProductVariant } from '@/api/queries'
import { BottomSheet } from '@shared/components/ui/BottomSheet'
import { ModalFooter } from '@shared/components/ui/Modal'
import type { ProductVariant, ProductVariantCreate, ProductVariantUpdate } from '@/types/product_variant'
import { PRODUCT_COLORS, PRODUCT_GAMMES } from '@/types/product_variant'
import { normalizeError } from '@shared/errors/normalizer'

const COLORS_ENUM = ['blanc', 'ivoire', 'bordeaux', 'noir', 'rouge', 'vert_amande', 'vert_sapin', 'taupe'] as const

const createSchema = z.object({
  color: z.enum(COLORS_ENUM).optional(),
  size: z.string().max(50, 'Max 50 caractères').optional(),
  gamme: z.string().max(50, 'Max 50 caractères').optional(),
  label: z.string().min(1, 'Label requis').max(100, 'Max 100 caractères'),
  price_per_day: z.number().min(0, 'Valeur positive').optional(),
  sku: z.string().min(1, 'SKU requis').max(50, 'Max 50 caractères'),
  stock_quantity: z.number().min(0, 'Valeur positive').default(0),
  available_quantity: z.number().min(0, 'Valeur positive').default(0),
}).refine((d) => d.color || d.size || d.gamme, {
  message: 'Au moins une dimension requise (couleur, taille ou gamme)',
  path: ['color'],
})

const updateSchema = z.object({
  color: z.enum(COLORS_ENUM).optional(),
  size: z.string().max(50).optional(),
  gamme: z.string().max(50).optional(),
  label: z.string().min(1).max(100).optional(),
  price_per_day: z.number().min(0).optional(),
  stock_quantity: z.number().min(0, 'Valeur positive').optional(),
  available_quantity: z.number().min(0, 'Valeur positive').optional(),
  is_active: z.boolean().optional(),
})

type CreateFormData = z.infer<typeof createSchema>
type UpdateFormData = z.infer<typeof updateSchema>

interface ProductVariantFormModalProps {
  isOpen: boolean
  onClose: () => void
  variant?: ProductVariant | null
  productId: number
  mode: 'create' | 'edit'
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function generateLabel(color?: string, size?: string, gamme?: string): string {
  return [gamme, size, color]
    .filter(Boolean)
    .map((s) => capitalize(s as string))
    .join(' ')
}

export function ProductVariantFormModal({
  isOpen,
  onClose,
  variant,
  productId,
  mode,
}: ProductVariantFormModalProps) {
  const isEdit = mode === 'edit'

  const createForm = useForm<CreateFormData>({
    resolver: zodResolver(createSchema),
    defaultValues: { sku: '', label: '', stock_quantity: 0, available_quantity: 0 },
  })

  const updateForm = useForm<UpdateFormData>({
    resolver: zodResolver(updateSchema),
  })

  useEffect(() => {
    if (!isOpen) return
    if (isEdit && variant) {
      updateForm.reset({
        color: variant.color as typeof COLORS_ENUM[number] | undefined,
        size: variant.size ?? undefined,
        gamme: variant.gamme ?? undefined,
        label: variant.label,
        price_per_day: variant.price_per_day ?? undefined,
        stock_quantity: variant.stock_quantity,
        available_quantity: variant.available_quantity,
        is_active: variant.is_active,
      })
    } else {
      createForm.reset({ sku: '', label: '', stock_quantity: 0, available_quantity: 0 })
    }
  }, [isOpen, variant, isEdit, createForm, updateForm])

  const createMutation = useCreateProductVariant(productId)
  const updateMutation = useUpdateProductVariant(productId)

  const handleGenerateLabel = useCallback(() => {
    const { color, size, gamme } = createForm.getValues()
    const generated = generateLabel(color, size, gamme)
    if (generated) {
      createForm.setValue('label', generated, { shouldValidate: true })
    }
  }, [createForm])

  const onSubmitCreate = (data: CreateFormData) => {
    createMutation.mutate(data as ProductVariantCreate, { onSuccess: onClose })
  }

  const onSubmitUpdate = (data: UpdateFormData) => {
    if (variant) {
      updateMutation.mutate({ id: variant.id, data }, { onSuccess: onClose })
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  const title = isEdit
    ? `Modifier la variante — ${variant?.label ?? ''}`
    : 'Nouvelle variante'

  return (
    <BottomSheet
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size="md"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={
            isEdit
              ? updateForm.handleSubmit(onSubmitUpdate)
              : createForm.handleSubmit(onSubmitCreate)
          }
          cancelText="Annuler"
          confirmText={isEdit ? 'Enregistrer' : 'Créer'}
          loading={isLoading}
        />
      }
    >
      <div className="space-y-4">
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {normalizeError(error).message || 'Une erreur est survenue'}
          </div>
        )}

        {!isEdit && (
          <>
            {/* Dimensions */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {/* Couleur */}
              <div>
                <label htmlFor="variant-color" className="block text-sm text-dark-400 mb-1">
                  Couleur
                </label>
                <select
                  id="variant-color"
                  {...createForm.register('color')}
                  className="input"
                >
                  <option value="">Aucune</option>
                  {PRODUCT_COLORS.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>

              {/* Taille */}
              <div>
                <label htmlFor="variant-size" className="block text-sm text-dark-400 mb-1">
                  Taille
                </label>
                <input
                  id="variant-size"
                  {...createForm.register('size')}
                  type="text"
                  className="input"
                  placeholder="ex: 21cm, 240cm"
                />
              </div>

              {/* Gamme */}
              <div>
                <label htmlFor="variant-gamme" className="block text-sm text-dark-400 mb-1">
                  Gamme
                </label>
                <select
                  id="variant-gamme"
                  {...createForm.register('gamme')}
                  className="input"
                >
                  <option value="">Aucune</option>
                  {PRODUCT_GAMMES.map((g) => (
                    <option key={g.value} value={g.value}>{g.label}</option>
                  ))}
                </select>
              </div>
            </div>
            {createForm.formState.errors.color && (
              <p className="text-red-500 text-sm -mt-2">
                {createForm.formState.errors.color.message}
              </p>
            )}

            {/* Label */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label htmlFor="variant-label" className="block text-sm text-dark-400">
                  Label *
                </label>
                <button
                  type="button"
                  onClick={handleGenerateLabel}
                  className="text-xs text-primary-400 hover:text-primary-300 transition-colors"
                >
                  Générer depuis dimensions
                </button>
              </div>
              <input
                id="variant-label"
                {...createForm.register('label')}
                type="text"
                className="input"
                placeholder="ex: Blanc, Classique 21cm"
              />
              {createForm.formState.errors.label && (
                <p className="text-red-500 text-sm mt-1">
                  {createForm.formState.errors.label.message}
                </p>
              )}
            </div>

            {/* SKU */}
            <div>
              <label htmlFor="variant-sku" className="block text-sm text-dark-400 mb-1">
                SKU *
              </label>
              <input
                id="variant-sku"
                {...createForm.register('sku')}
                type="text"
                className="input"
                placeholder="NAP-RND-240-IVO"
              />
              {createForm.formState.errors.sku && (
                <p className="text-red-500 text-sm mt-1">
                  {createForm.formState.errors.sku.message}
                </p>
              )}
            </div>

            {/* Prix override */}
            <div>
              <label htmlFor="variant-price" className="block text-sm text-dark-400 mb-1">
                Prix override (centimes)
              </label>
              <input
                id="variant-price"
                {...createForm.register('price_per_day', { valueAsNumber: true })}
                type="number"
                className="input"
                min={0}
                placeholder="Hérite du produit parent si vide"
              />
              {createForm.formState.errors.price_per_day && (
                <p className="text-red-500 text-sm mt-1">
                  {createForm.formState.errors.price_per_day.message}
                </p>
              )}
            </div>

            {/* Stock */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="variant-create-stock" className="block text-sm text-dark-400 mb-1">
                  Stock total
                </label>
                <input
                  id="variant-create-stock"
                  {...createForm.register('stock_quantity', { valueAsNumber: true })}
                  type="number"
                  className="input"
                  min={0}
                  placeholder="0"
                />
              </div>
              <div>
                <label htmlFor="variant-create-available" className="block text-sm text-dark-400 mb-1">
                  Quantité disponible
                </label>
                <input
                  id="variant-create-available"
                  {...createForm.register('available_quantity', { valueAsNumber: true })}
                  type="number"
                  className="input"
                  min={0}
                  placeholder="0"
                />
              </div>
            </div>
          </>
        )}

        {isEdit && (
          <>
            {/* Dimensions éditables */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div>
                <label htmlFor="edit-color" className="block text-sm text-dark-400 mb-1">
                  Couleur
                </label>
                <select
                  id="edit-color"
                  {...updateForm.register('color')}
                  className="input"
                >
                  <option value="">Aucune</option>
                  {PRODUCT_COLORS.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="edit-size" className="block text-sm text-dark-400 mb-1">
                  Taille
                </label>
                <input
                  id="edit-size"
                  {...updateForm.register('size')}
                  type="text"
                  className="input"
                  placeholder="ex: 21cm"
                />
              </div>
              <div>
                <label htmlFor="edit-gamme" className="block text-sm text-dark-400 mb-1">
                  Gamme
                </label>
                <select
                  id="edit-gamme"
                  {...updateForm.register('gamme')}
                  className="input"
                >
                  <option value="">Aucune</option>
                  {PRODUCT_GAMMES.map((g) => (
                    <option key={g.value} value={g.value}>{g.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Label */}
            <div>
              <label htmlFor="edit-label" className="block text-sm text-dark-400 mb-1">
                Label
              </label>
              <input
                id="edit-label"
                {...updateForm.register('label')}
                type="text"
                className="input"
              />
              {updateForm.formState.errors.label && (
                <p className="text-red-500 text-sm mt-1">
                  {updateForm.formState.errors.label.message}
                </p>
              )}
            </div>

            {/* Prix override */}
            <div>
              <label htmlFor="edit-price" className="block text-sm text-dark-400 mb-1">
                Prix override (centimes)
              </label>
              <input
                id="edit-price"
                {...updateForm.register('price_per_day', { valueAsNumber: true })}
                type="number"
                className="input"
                min={0}
                placeholder="Hérite du produit parent si vide"
              />
            </div>

            {/* Stock */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="variant-edit-stock" className="block text-sm text-dark-400 mb-1">
                  Stock total
                </label>
                <input
                  id="variant-edit-stock"
                  {...updateForm.register('stock_quantity', { valueAsNumber: true })}
                  type="number"
                  className="input"
                  min={0}
                />
              </div>
              <div>
                <label htmlFor="variant-edit-available" className="block text-sm text-dark-400 mb-1">
                  Quantité disponible
                </label>
                <input
                  id="variant-edit-available"
                  {...updateForm.register('available_quantity', { valueAsNumber: true })}
                  type="number"
                  className="input"
                  min={0}
                />
              </div>
            </div>

            {/* Statut actif */}
            <div>
              <label htmlFor="variant-is-active" className="flex items-center gap-2 cursor-pointer">
                <input
                  id="variant-is-active"
                  {...updateForm.register('is_active')}
                  type="checkbox"
                  className="w-4 h-4 rounded border-dark-600 bg-dark-900 text-primary-600 focus:ring-primary-600"
                />
                <span className="text-sm text-dark-300">Variante active</span>
              </label>
            </div>
          </>
        )}
      </div>
    </BottomSheet>
  )
}
