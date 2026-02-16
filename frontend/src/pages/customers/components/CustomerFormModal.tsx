import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { customersApi } from '@/api/customers'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { CustomerList, CustomerCreate, CustomerUpdate } from '@/types/customer'

const customerSchema = z.object({
  customer_type: z.enum(['individual', 'company']),
  email: z.string().email('Email invalide'),
  phone: z.string().optional().default(''),
  first_name: z.string().optional().default(''),
  last_name: z.string().optional().default(''),
  company_name: z.string().optional().default(''),
  address: z.string().optional().default(''),
  city: z.string().optional().default(''),
  postal_code: z.string().optional().default(''),
  country: z.string().optional().default('France'),
}).superRefine((data, ctx) => {
  if (data.customer_type === 'individual' && !data.last_name) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Nom requis pour un particulier',
      path: ['last_name'],
    })
  }
  if (data.customer_type === 'company' && !data.company_name) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Raison sociale requise pour une entreprise',
      path: ['company_name'],
    })
  }
})

type CustomerFormData = z.infer<typeof customerSchema>

interface CustomerFormModalProps {
  isOpen: boolean
  onClose: () => void
  customer?: CustomerList | null
  mode: 'create' | 'edit'
}

export function CustomerFormModal({
  isOpen,
  onClose,
  customer,
  mode,
}: CustomerFormModalProps) {
  const queryClient = useQueryClient()
  const isEdit = mode === 'edit'

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<CustomerFormData>({
    resolver: zodResolver(customerSchema),
    defaultValues: {
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
    },
  })

  const customerType = watch('customer_type')

  useEffect(() => {
    if (isOpen) {
      if (customer) {
        reset({
          customer_type: customer.customer_type,
          email: customer.email,
          phone: customer.phone || '',
          first_name: customer.first_name || '',
          last_name: customer.last_name || '',
          company_name: customer.company_name || '',
          address: '',
          city: customer.city || '',
          postal_code: '',
          country: customer.country || 'France',
        })
      } else {
        reset({
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
        })
      }
    }
  }, [isOpen, customer, reset])

  const createMutation = useMutation({
    mutationFn: (data: CustomerCreate) => customersApi.createCustomer(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      onClose()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: CustomerUpdate }) =>
      customersApi.updateCustomer(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      onClose()
    },
  })

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
    }

    if (isEdit && customer) {
      updateMutation.mutate({ id: customer.id, data: payload as CustomerUpdate })
    } else {
      createMutation.mutate(payload as CustomerCreate)
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
          confirmText={isEdit ? 'Enregistrer' : 'Creer'}
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
            Type de client *
          </label>
          <select {...register('customer_type')} className="input w-full">
            <option value="individual">Particulier</option>
            <option value="company">Entreprise</option>
          </select>
        </div>

        {customerType === 'individual' ? (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-1">
                Prenom
              </label>
              <input
                {...register('first_name')}
                type="text"
                className="input w-full"
                placeholder="Jean"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-1">
                Nom *
              </label>
              <input
                {...register('last_name')}
                type="text"
                className="input w-full"
                placeholder="Dupont"
              />
              {errors.last_name && (
                <p className="text-red-500 text-sm mt-1">{errors.last_name.message}</p>
              )}
            </div>
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Raison sociale *
            </label>
            <input
              {...register('company_name')}
              type="text"
              className="input w-full"
              placeholder="SARL Exemple"
            />
            {errors.company_name && (
              <p className="text-red-500 text-sm mt-1">{errors.company_name.message}</p>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Email *
            </label>
            <input
              {...register('email')}
              type="email"
              className="input w-full"
              placeholder="contact@exemple.com"
            />
            {errors.email && (
              <p className="text-red-500 text-sm mt-1">{errors.email.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Telephone
            </label>
            <input
              {...register('phone')}
              type="tel"
              className="input w-full"
              placeholder="06 12 34 56 78"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Adresse
          </label>
          <input
            {...register('address')}
            type="text"
            className="input w-full"
            placeholder="123 rue de la Paix"
          />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Code postal
            </label>
            <input
              {...register('postal_code')}
              type="text"
              className="input w-full"
              placeholder="75001"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Ville
            </label>
            <input
              {...register('city')}
              type="text"
              className="input w-full"
              placeholder="Paris"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Pays
            </label>
            <input
              {...register('country')}
              type="text"
              className="input w-full"
              placeholder="France"
            />
          </div>
        </div>
      </form>
    </Modal>
  )
}
