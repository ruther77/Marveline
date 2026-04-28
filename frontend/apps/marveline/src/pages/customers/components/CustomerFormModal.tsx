import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useCreateCustomer, useUpdateCustomer } from '@/api/queries'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import type { CustomerList, CustomerResponse, CustomerCreate, CustomerUpdate } from '@/types/customer'
import { normalizeError } from '@shared/errors/normalizer'

const ORG_TYPES = ['company', 'professional', 'association'] as const

const customerSchema = z.object({
  customer_type: z.enum(['individual', 'company', 'professional', 'association']),
  email: z.string().email('Email invalide'),
  phone: z.string().optional().default(''),
  first_name: z.string().optional().default(''),
  last_name: z.string().optional().default(''),
  company_name: z.string().optional().default(''),
  address: z.string().optional().default(''),
  city: z.string().optional().default(''),
  postal_code: z.string().optional().default(''),
  country: z.string().optional().default('France'),
  notes: z.string().max(2000).optional().default(''),
}).superRefine((data, ctx) => {
  if (data.customer_type === 'individual') {
    if (!data.last_name) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Nom requis pour un particulier',
        path: ['last_name'],
      })
    }
  } else if ((ORG_TYPES as readonly string[]).includes(data.customer_type)) {
    if (!data.company_name) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Raison sociale requise',
        path: ['company_name'],
      })
    }
  }
})

type CustomerFormData = z.infer<typeof customerSchema>

const EMPTY_DEFAULTS: CustomerFormData = {
  customer_type: 'individual',
  email: '',
  phone: '',
  first_name: '',
  last_name: '',
  company_name: '',
  address: '',
  city: '',
  postal_code: '',
  country: 'France',
  notes: '',
}

interface CustomerFormModalProps {
  isOpen: boolean
  onClose: () => void
  customer?: CustomerList | CustomerResponse | null
  mode: 'create' | 'edit'
}

export function CustomerFormModal({
  isOpen,
  onClose,
  customer,
  mode,
}: CustomerFormModalProps) {
  const isEdit = mode === 'edit'

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<CustomerFormData>({
    resolver: zodResolver(customerSchema),
    defaultValues: EMPTY_DEFAULTS,
  })

  const customerType = watch('customer_type')
  const isOrg = (ORG_TYPES as readonly string[]).includes(customerType)

  useEffect(() => {
    if (!isOpen) return
    if (customer) {
      reset({
        customer_type: customer.customer_type,
        email: customer.email,
        phone: customer.phone || '',
        first_name: customer.first_name || '',
        last_name: customer.last_name || '',
        company_name: customer.company_name || '',
        address: customer.address || '',
        city: customer.city || '',
        postal_code: customer.postal_code || '',
        country: customer.country || 'France',
        notes: customer.notes || '',
      })
    } else {
      reset(EMPTY_DEFAULTS)
    }
  }, [isOpen, customer, reset])

  const createMutation = useCreateCustomer()
  const updateMutation = useUpdateCustomer()

  const onSubmit = (formData: CustomerFormData) => {
    const payload = {
      ...formData,
      phone: formData.phone || undefined,
      first_name: formData.first_name || undefined,
      last_name: formData.last_name || undefined,
      company_name: formData.company_name || undefined,
      address: formData.address || undefined,
      city: formData.city || undefined,
      postal_code: formData.postal_code || undefined,
      notes: formData.notes || undefined,
    }

    if (isEdit && customer) {
      updateMutation.mutate({ id: customer.id, data: payload as CustomerUpdate }, { onSuccess: onClose })
    } else {
      createMutation.mutate(payload as CustomerCreate, { onSuccess: onClose })
    }
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier le client' : 'Nouveau client'}
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
        {error != null && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {normalizeError(error).message || 'Une erreur est survenue'}
          </div>
        )}

        {/* Type de client */}
        <div>
          <label htmlFor="customer_type" className="block text-sm text-dark-400 mb-1">
            Type de client
          </label>
          <select id="customer_type" {...register('customer_type')} className="input">
            <option value="individual">Particulier</option>
            <option value="company">Entreprise</option>
            <option value="professional">Professionnel</option>
            <option value="association">Association / Comité</option>
          </select>
        </div>

        {/* Champs conditionnels selon type */}
        {!isOrg ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="first_name" className="block text-sm text-dark-400 mb-1">Prénom</label>
              <input
                id="first_name"
                {...register('first_name')}
                type="text"
                className="input"
                placeholder="Jean"
              />
            </div>
            <div>
              <label htmlFor="last_name" className="block text-sm text-dark-400 mb-1">
                Nom <span className="text-red-400">*</span>
              </label>
              <input
                id="last_name"
                {...register('last_name')}
                type="text"
                className="input"
                placeholder="Dupont"
              />
              {errors.last_name && (
                <p className="text-red-400 text-xs mt-1">{errors.last_name.message}</p>
              )}
            </div>
          </div>
        ) : (
          <div>
            <label htmlFor="company_name" className="block text-sm text-dark-400 mb-1">
              Raison sociale <span className="text-red-400">*</span>
            </label>
            <input
              id="company_name"
              {...register('company_name')}
              type="text"
              className="input"
              placeholder="SARL Exemple"
            />
            {errors.company_name && (
              <p className="text-red-400 text-xs mt-1">{errors.company_name.message}</p>
            )}
          </div>
        )}

        {/* Contact */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="email" className="block text-sm text-dark-400 mb-1">
              Email <span className="text-red-400">*</span>
            </label>
            <input
              id="email"
              {...register('email')}
              type="email"
              className="input"
              placeholder="contact@exemple.com"
            />
            {errors.email && (
              <p className="text-red-400 text-xs mt-1">{errors.email.message}</p>
            )}
          </div>
          <div>
            <label htmlFor="phone" className="block text-sm text-dark-400 mb-1">Téléphone</label>
            <input
              id="phone"
              {...register('phone')}
              type="tel"
              className="input"
              placeholder="06 12 34 56 78"
            />
          </div>
        </div>

        {/* Adresse */}
        <div>
          <label htmlFor="address" className="block text-sm text-dark-400 mb-1">Adresse</label>
          <input
            id="address"
            {...register('address')}
            type="text"
            className="input"
            placeholder="123 rue de la Paix"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label htmlFor="postal_code" className="block text-sm text-dark-400 mb-1">Code postal</label>
            <input
              id="postal_code"
              {...register('postal_code')}
              type="text"
              className="input"
              placeholder="75001"
            />
          </div>
          <div>
            <label htmlFor="city" className="block text-sm text-dark-400 mb-1">Ville</label>
            <input
              id="city"
              {...register('city')}
              type="text"
              className="input"
              placeholder="Paris"
            />
          </div>
          <div>
            <label htmlFor="country" className="block text-sm text-dark-400 mb-1">Pays</label>
            <input
              id="country"
              {...register('country')}
              type="text"
              className="input"
              placeholder="France"
            />
          </div>
        </div>

        {/* Note interne */}
        <div>
          <label htmlFor="notes" className="block text-sm text-dark-400 mb-1">
            Note interne
            <span className="ml-1 text-xs text-dark-500">(non visible par le client)</span>
          </label>
          <textarea
            id="notes"
            {...register('notes')}
            rows={3}
            className="input resize-none"
            placeholder="Préférences, informations utiles pour l'équipe…"
          />
          {errors.notes && (
            <p className="text-red-400 text-xs mt-1">{errors.notes.message}</p>
          )}
        </div>
      </form>
    </Modal>
  )
}
