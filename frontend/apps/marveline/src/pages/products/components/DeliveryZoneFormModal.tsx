import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useCreateDeliveryZone, useUpdateDeliveryZone } from '@/api/queries'
import { BottomSheet } from '@shared/components/ui/BottomSheet'
import { ModalFooter } from '@shared/components/ui/Modal'
import type { DeliveryZone, DeliveryZoneCreate, DeliveryZoneUpdate } from '@/types/delivery_zone'
import { normalizeError } from '@shared/errors/normalizer'

const formSchema = z.object({
  department_code: z.string().min(2, 'Code requis (ex: 60)').max(3, 'Max 3 caractères'),
  department_name: z.string().min(1, 'Nom du département requis'),
  delivery_fee_cents: z.number().min(0, 'Montant positif requis'),
  sunday_surcharge_cents: z.number().min(0, 'Montant positif requis'),
  notes: z.string().optional(),
  is_active: z.boolean().default(true),
})

type FormData = z.infer<typeof formSchema>

interface DeliveryZoneFormModalProps {
  isOpen: boolean
  onClose: () => void
  zone?: DeliveryZone | null
  mode: 'create' | 'edit'
}

export function DeliveryZoneFormModal({
  isOpen,
  onClose,
  zone,
  mode,
}: DeliveryZoneFormModalProps) {
  const isEdit = mode === 'edit'

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      department_code: '',
      department_name: '',
      delivery_fee_cents: 0,
      sunday_surcharge_cents: 0,
      notes: '',
      is_active: true,
    },
  })

  useEffect(() => {
    if (isOpen) {
      if (zone) {
        reset({
          department_code: zone.department_code,
          department_name: zone.department_name,
          delivery_fee_cents: zone.delivery_fee_cents,
          sunday_surcharge_cents: zone.sunday_surcharge_cents,
          notes: zone.notes || '',
          is_active: zone.is_active,
        })
      } else {
        reset({
          department_code: '',
          department_name: '',
          delivery_fee_cents: 0,
          sunday_surcharge_cents: 0,
          notes: '',
          is_active: true,
        })
      }
    }
  }, [isOpen, zone, reset])

  const createMutation = useCreateDeliveryZone()
  const updateMutation = useUpdateDeliveryZone()

  const onSubmit = (data: FormData) => {
    const payload = {
      ...data,
      notes: data.notes || undefined,
    }
    if (isEdit && zone) {
      updateMutation.mutate({ id: zone.id, data: payload as DeliveryZoneUpdate }, { onSuccess: onClose })
    } else {
      createMutation.mutate(payload as DeliveryZoneCreate, { onSuccess: onClose })
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <BottomSheet
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier la zone de livraison' : 'Nouvelle zone de livraison'}
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

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="zone-department-code" className="block text-sm text-dark-400 mb-1">
              Code département *
            </label>
            <input
              id="zone-department-code"
              {...register('department_code')}
              type="text"
              className="input"
              placeholder="60"
              maxLength={3}
            />
            {errors.department_code && (
              <p className="text-red-500 text-sm mt-1">{errors.department_code.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="zone-department-name" className="block text-sm text-dark-400 mb-1">
              Nom du département *
            </label>
            <input
              id="zone-department-name"
              {...register('department_name')}
              type="text"
              className="input"
              placeholder="Oise"
            />
            {errors.department_name && (
              <p className="text-red-500 text-sm mt-1">{errors.department_name.message}</p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="zone-delivery-fee" className="block text-sm text-dark-400 mb-1">
              Frais de livraison (centimes) *
            </label>
            <input
              id="zone-delivery-fee"
              {...register('delivery_fee_cents', { valueAsNumber: true })}
              type="number"
              className="input"
              placeholder="0 (sur devis)"
              min={0}
            />
            <p className="text-xs text-dark-400 mt-1">0 = sur devis</p>
            {errors.delivery_fee_cents && (
              <p className="text-red-500 text-sm mt-1">{errors.delivery_fee_cents.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="zone-sunday-surcharge" className="block text-sm text-dark-400 mb-1">
              Supplément dimanche (centimes)
            </label>
            <input
              id="zone-sunday-surcharge"
              {...register('sunday_surcharge_cents', { valueAsNumber: true })}
              type="number"
              className="input"
              placeholder="0"
              min={0}
            />
            {errors.sunday_surcharge_cents && (
              <p className="text-red-500 text-sm mt-1">{errors.sunday_surcharge_cents.message}</p>
            )}
          </div>
        </div>

        <div>
          <label htmlFor="zone-notes" className="block text-sm text-dark-400 mb-1">
            Notes
          </label>
          <textarea
            id="zone-notes"
            {...register('notes')}
            className="input"
            rows={2}
            placeholder="Informations complémentaires..."
          />
        </div>

        {isEdit && (
          <div>
            <label htmlFor="zone-is-active" className="flex items-center gap-2 cursor-pointer">
              <input
                id="zone-is-active"
                {...register('is_active')}
                type="checkbox"
                className="w-4 h-4 rounded border-dark-600 bg-dark-900 text-primary-600 focus:ring-primary-600"
              />
              <span className="text-sm text-dark-300">Zone active</span>
            </label>
          </div>
        )}
      </form>
    </BottomSheet>
  )
}
