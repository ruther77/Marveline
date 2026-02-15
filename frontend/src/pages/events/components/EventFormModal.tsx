import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { reservationsApi } from '@/api/reservations'
import { customersApi } from '@/api/customers'
import { productsApi } from '@/api/products'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import type { ReservationList, ReservationCreate, ReservationUpdate } from '@/types/reservation'
import type { Product } from '@/types/product'
import { Plus, X } from 'lucide-react'

const reservationSchema = z.object({
  customer_id: z.number({ required_error: 'Client requis' }).min(1, 'Client requis'),
  event_date: z.string().min(1, 'Date evenement requise'),
  delivery_date: z.string().min(1, 'Date livraison requise'),
  return_date: z.string().min(1, 'Date retour requise'),
  event_location: z.string().optional(),
  notes: z.string().optional(),
}).refine(
  (data) => !data.delivery_date || !data.event_date || data.delivery_date <= data.event_date,
  { message: 'La livraison doit etre avant ou le jour de l\'evenement', path: ['delivery_date'] }
).refine(
  (data) => !data.return_date || !data.event_date || data.return_date >= data.event_date,
  { message: 'Le retour doit etre apres ou le jour de l\'evenement', path: ['return_date'] }
)

type FormData = z.infer<typeof reservationSchema>

interface LineItem {
  product_id: number
  quantity: number
}

interface ReservationFormModalProps {
  isOpen: boolean
  onClose: () => void
  reservation?: Partial<ReservationList> | null
  mode: 'create' | 'edit'
}

export function ReservationFormModal({ isOpen, onClose, reservation, mode }: ReservationFormModalProps) {
  const queryClient = useQueryClient()
  const isEdit = mode === 'edit'
  const [lines, setLines] = useState<LineItem[]>([{ product_id: 0, quantity: 1 }])
  const [customerSearch, setCustomerSearch] = useState('')

  const { register, handleSubmit, reset, setValue, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(reservationSchema),
  })

  const { data: customersData } = useQuery({
    queryKey: ['customers-select', customerSearch],
    queryFn: () => customersApi.getCustomers({ page_size: 50, search_query: customerSearch || undefined }),
    enabled: isOpen,
  })

  const { data: productsData } = useQuery({
    queryKey: ['products-select'],
    queryFn: () => productsApi.getProducts({ page_size: 200, active_only: true }),
    enabled: isOpen,
  })

  const customers = customersData?.items || []
  const products = productsData?.items || []

  useEffect(() => {
    if (isOpen && reservation && isEdit) {
      reset({
        customer_id: reservation.customer_id || 0,
        event_date: reservation.event_date?.split('T')[0] || '',
        delivery_date: reservation.delivery_date?.split('T')[0] || '',
        return_date: reservation.return_date?.split('T')[0] || '',
        event_location: reservation.event_location || '',
        notes: reservation.notes || '',
      })
      setLines([])
    } else if (isOpen && !isEdit) {
      reset({
        customer_id: 0,
        event_date: '',
        delivery_date: '',
        return_date: '',
        event_location: '',
        notes: '',
      })
      setLines([{ product_id: 0, quantity: 1 }])
    }
  }, [isOpen, reservation, isEdit, reset])

  const createMutation = useMutation({
    mutationFn: (data: ReservationCreate) => reservationsApi.createReservation(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reservations'] })
      onClose()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ReservationUpdate }) =>
      reservationsApi.updateReservation(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reservations'] })
      onClose()
    },
  })

  const onSubmit = (data: FormData) => {
    if (isEdit && reservation?.id) {
      const updateData: ReservationUpdate = {
        event_date: data.event_date,
        delivery_date: data.delivery_date,
        return_date: data.return_date,
        event_location: data.event_location || undefined,
      }
      updateMutation.mutate({ id: reservation.id, data: updateData })
    } else {
      const validLines = lines.filter((l) => l.product_id > 0 && l.quantity > 0)
      const createData: ReservationCreate = {
        customer_id: data.customer_id,
        event_date: data.event_date,
        delivery_date: data.delivery_date,
        return_date: data.return_date,
        event_location: data.event_location || undefined,
        notes: data.notes || undefined,
        lines: validLines,
      }
      createMutation.mutate(createData)
    }
  }

  const addLine = () => {
    setLines([...lines, { product_id: 0, quantity: 1 }])
  }

  const removeLine = (index: number) => {
    setLines(lines.filter((_, i) => i !== index))
  }

  const updateLine = (index: number, field: keyof LineItem, value: number) => {
    const updated = [...lines]
    updated[index] = { ...updated[index], [field]: value }
    setLines(updated)
  }

  const getProductPrice = (productId: number): Product | undefined => {
    return products.find((p) => p.id === productId)
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier la reservation' : 'Nouvelle reservation'}
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

        {/* Client */}
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Client *
          </label>
          {!isEdit ? (
            <>
              <input
                type="text"
                placeholder="Rechercher un client..."
                value={customerSearch}
                onChange={(e) => setCustomerSearch(e.target.value)}
                className="input w-full mb-2"
              />
              <select
                className="input w-full"
                onChange={(e) => setValue('customer_id', Number(e.target.value), { shouldValidate: true })}
              >
                <option value={0}>-- Selectionner un client --</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.display_name} ({c.email})
                  </option>
                ))}
              </select>
              {errors.customer_id && (
                <p className="text-red-500 text-sm mt-1">{errors.customer_id.message}</p>
              )}
            </>
          ) : (
            <p className="text-sm text-dark-400">
              Client #{reservation?.customer_id} (non modifiable)
            </p>
          )}
        </div>

        {/* Dates */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Date evenement *
            </label>
            <input {...register('event_date')} type="date" className="input w-full" />
            {errors.event_date && (
              <p className="text-red-500 text-sm mt-1">{errors.event_date.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Livraison *
            </label>
            <input {...register('delivery_date')} type="date" className="input w-full" />
            {errors.delivery_date && (
              <p className="text-red-500 text-sm mt-1">{errors.delivery_date.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Retour *
            </label>
            <input {...register('return_date')} type="date" className="input w-full" />
            {errors.return_date && (
              <p className="text-red-500 text-sm mt-1">{errors.return_date.message}</p>
            )}
          </div>
        </div>

        {/* Lieu */}
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Lieu de l'evenement
          </label>
          <input {...register('event_location')} type="text" className="input w-full" placeholder="Adresse ou nom du lieu" />
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1">
            Notes
          </label>
          <textarea {...register('notes')} className="input w-full" rows={2} placeholder="Notes internes..." />
        </div>

        {/* Lines (creation only) */}
        {!isEdit && (
          <div className="border-t border-dark-700 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-dark-300">Produits</h3>
              <button
                type="button"
                onClick={addLine}
                className="btn-secondary btn-sm flex items-center gap-1"
              >
                <Plus className="w-3 h-3" />
                Ajouter
              </button>
            </div>

            {lines.length === 0 && (
              <p className="text-sm text-dark-500 text-center py-4">
                Aucun produit ajoute
              </p>
            )}

            <div className="space-y-2">
              {lines.map((line, index) => {
                const product = getProductPrice(line.product_id)
                return (
                  <div key={index} className="flex items-center gap-2">
                    <select
                      value={line.product_id}
                      onChange={(e) => updateLine(index, 'product_id', Number(e.target.value))}
                      className="input flex-1"
                    >
                      <option value={0}>-- Produit --</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.price_per_day_euros.toFixed(2)} EUR/j)
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      min={1}
                      value={line.quantity}
                      onChange={(e) => updateLine(index, 'quantity', Number(e.target.value))}
                      className="input w-20"
                    />
                    {product && (
                      <span className="text-sm text-dark-400 w-24 text-right">
                        {(product.price_per_day_euros * line.quantity).toFixed(2)} EUR
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => removeLine(index)}
                      className="p-1 hover:bg-dark-700 rounded text-dark-400 hover:text-red-500"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {isEdit && (
          <div className="border-t border-dark-700 pt-4">
            <p className="text-sm text-dark-500">
              Les lignes de produits ne sont pas modifiables apres creation.
            </p>
          </div>
        )}
      </form>
    </Modal>
  )
}
