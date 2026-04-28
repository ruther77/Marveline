import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { normalizeError } from '@shared/errors/normalizer'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useCustomersList, useProductsList, useProductVariantsList, useCreateReservation, useUpdateReservation } from '@/api/queries'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { ActionError } from '@shared/components/ui/ActionError'
import type { ReservationList, ReservationCreate, ReservationUpdate } from '@/types/reservation'
import type { Product } from '@/types/product'
import { AlertTriangle, Plus, X } from 'lucide-react'
import { PAGE_SIZE_SELECT } from '@/lib/constants'
import { formatCurrency } from '@/lib/utils'

const EVENT_TYPES = [
  { value: 'mariage', label: 'Mariage' },
  { value: 'anniversaire', label: 'Anniversaire' },
  { value: 'entreprise', label: 'Entreprise' },
  { value: 'autre', label: 'Autre' },
] as const

const reservationSchema = z.object({
  customer_id: z.number({ required_error: 'Client requis' }).min(1, 'Client requis'),
  event_date: z.string().min(1, 'Date evenement requise'),
  delivery_date: z.string().min(1, 'Date livraison requise'),
  return_date: z.string().min(1, 'Date retour requise'),
  event_location: z.string().optional(),
  event_type: z.enum(['mariage', 'anniversaire', 'entreprise', 'autre']).optional(),
  event_name: z.string().max(200).optional(),
  guest_count: z.number().int().min(1).optional().nullable(),
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
  variant_id?: number
}

function VariantSelect({ productId, value, onChange }: {
  productId: number
  value?: number
  onChange: (v: number | undefined) => void
}) {
  const { data: variants = [] } = useProductVariantsList(productId)
  if (variants.length <= 1) {
    if (variants.length === 1 && value !== variants[0].id) onChange(variants[0].id)
    return null
  }
  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : undefined)}
      className="input text-xs py-1 w-32"
      aria-label="Variante"
    >
      <option value="">Variante…</option>
      {variants.map((v) => (
        <option key={v.id} value={v.id}>{v.label} ({v.available_quantity})</option>
      ))}
    </select>
  )
}

interface ReservationFormModalProps {
  isOpen: boolean
  onClose: () => void
  reservation?: Partial<ReservationList> | null
  mode: 'create' | 'edit'
}

export function ReservationFormModal({ isOpen, onClose, reservation, mode }: ReservationFormModalProps) {
  const isEdit = mode === 'edit'
  const [lines, setLines] = useState<LineItem[]>([{ product_id: 0, quantity: 1 }])
  const [customerSearch, setCustomerSearch] = useState('')

  const { register, handleSubmit, reset, setValue, watch, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(reservationSchema),
  })

  const watchedEventDate = watch('event_date')
  const watchedDeliveryDate = watch('delivery_date')
  const watchedReturnDate = watch('return_date')

  const rentalDays = (() => {
    if (!watchedDeliveryDate || !watchedReturnDate) return 1
    const diff = (new Date(watchedReturnDate).getTime() - new Date(watchedDeliveryDate).getTime()) / 86400000
    return Math.max(1, Math.floor(diff) + 1)
  })()

  const { data: customersData } = useCustomersList({ limit: 50, search_query: customerSearch || undefined }, isOpen)
  const { data: productsData } = useProductsList({ limit: PAGE_SIZE_SELECT, active_only: true }, isOpen)

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
        event_type: reservation.event_type ?? undefined,
        event_name: reservation.event_name || '',
        guest_count: reservation.guest_count ?? null,
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
        event_type: undefined,
        event_name: '',
        guest_count: null,
        notes: '',
      })
      setLines([{ product_id: 0, quantity: 1 }])
    }
  }, [isOpen, reservation, isEdit, reset])

  const createMutation = useCreateReservation()
  const updateMutation = useUpdateReservation()

  const onSubmit = (data: FormData) => {
    if (isEdit && reservation?.id) {
      const updateData: ReservationUpdate = {
        event_date: data.event_date,
        delivery_date: data.delivery_date,
        return_date: data.return_date,
        event_location: data.event_location || undefined,
        event_type: data.event_type ?? undefined,
        event_name: data.event_name || undefined,
        guest_count: data.guest_count ?? undefined,
      }
      updateMutation.mutate({ id: reservation.id, data: updateData }, { onSuccess: onClose })
    } else {
      const validLines = lines.filter((l) => l.product_id > 0 && l.quantity > 0)
      if (validLines.some((l) => !l.variant_id)) return
      const createData: ReservationCreate = {
        customer_id: data.customer_id,
        event_date: data.event_date,
        delivery_date: data.delivery_date,
        return_date: data.return_date,
        event_location: data.event_location || undefined,
        event_type: data.event_type ?? undefined,
        event_name: data.event_name || undefined,
        guest_count: data.guest_count ?? undefined,
        notes: data.notes || undefined,
        lines: validLines.map((l) => ({ product_id: l.product_id, quantity: l.quantity, variant_id: l.variant_id })),
      }
      createMutation.mutate(createData, { onSuccess: onClose })
    }
  }

  const addLine = () => {
    setLines([...lines, { product_id: 0, quantity: 1 }])
  }

  const removeLine = (index: number) => {
    setLines(lines.filter((_, i) => i !== index))
  }

  const updateLine = (index: number, field: keyof LineItem, value: number | undefined) => {
    const updated = [...lines]
    if (field === 'product_id') {
      updated[index] = { ...updated[index], product_id: value as number, variant_id: undefined }
    } else {
      updated[index] = { ...updated[index], [field]: value }
    }
    setLines(updated)
  }

  const getProductPrice = (productId: number): Product | undefined => {
    return products.find((p) => p.id === productId)
  }

  const isLoading = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  const hasLinenProduct = lines.some((line) => {
    if (!line.product_id) return false
    const product = products.find((p) => p.id === line.product_id)
    return product?.category === 'NAPPES'
  })

  const isEventTooSoon = (() => {
    if (!watchedEventDate) return false
    const eventDate = new Date(watchedEventDate)
    const minDate = new Date(Date.now() + 90 * 24 * 60 * 60 * 1000)
    return eventDate < minDate
  })()

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
          confirmText={isEdit ? 'Enregistrer' : 'Créer'}
          loading={isLoading}
        />
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
        <ActionError
          message={(error ? normalizeError(error).message || 'Une erreur est survenue' : null)}
          onDismiss={() => { createMutation.reset(); updateMutation.reset() }}
        />

        {/* Client */}
        <div>
          <label htmlFor="customer_id" className="block text-sm text-dark-400 mb-1">
            Client *
          </label>
          {!isEdit ? (
            <>
              <input
                type="text"
                placeholder="Rechercher un client..."
                aria-label="Rechercher un client"
                value={customerSearch}
                onChange={(e) => setCustomerSearch(e.target.value)}
                className="input w-full mb-2"
              />
              <select
                id="customer_id"
                className="input"
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
              {reservation?.customer_name || `Client #${reservation?.customer_id}`} (non modifiable)
            </p>
          )}
        </div>

        {/* Dates */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label htmlFor="event_date" className="block text-sm text-dark-400 mb-1">
              Date evenement *
            </label>
            <input id="event_date" {...register('event_date')} type="date" className="input" />
            {errors.event_date && (
              <p className="text-red-500 text-sm mt-1">{errors.event_date.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="delivery_date" className="block text-sm text-dark-400 mb-1">
              Livraison *
            </label>
            <input id="delivery_date" {...register('delivery_date')} type="date" className="input" />
            {errors.delivery_date && (
              <p className="text-red-500 text-sm mt-1">{errors.delivery_date.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="return_date" className="block text-sm text-dark-400 mb-1">
              Retour *
            </label>
            <input id="return_date" {...register('return_date')} type="date" className="input" />
            {errors.return_date && (
              <p className="text-red-500 text-sm mt-1">{errors.return_date.message}</p>
            )}
          </div>
        </div>

        {/* Lieu */}
        <div>
          <label htmlFor="event_location" className="block text-sm text-dark-400 mb-1">
            Lieu de l'evenement
          </label>
          <input id="event_location" {...register('event_location')} type="text" className="input" placeholder="Adresse ou nom du lieu" />
        </div>

        {/* Détails événement */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label htmlFor="event_type" className="block text-sm text-dark-400 mb-1">
              Type d'evenement
            </label>
            <select id="event_type" {...register('event_type')} className="input">
              <option value="">-- Selectionner --</option>
              {EVENT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="event_name" className="block text-sm text-dark-400 mb-1">
              Nom de l'evenement
            </label>
            <input
              id="event_name"
              {...register('event_name')}
              type="text"
              className="input"
              placeholder="ex: Mariage Dupont"
            />
          </div>
          <div>
            <label htmlFor="guest_count" className="block text-sm text-dark-400 mb-1">
              Nombre d'invites
            </label>
            <input
              id="guest_count"
              {...register('guest_count', { valueAsNumber: true })}
              type="number"
              min={1}
              className="input"
              placeholder="ex: 120"
            />
            {errors.guest_count && (
              <p className="text-red-500 text-sm mt-1">{errors.guest_count.message}</p>
            )}
          </div>
        </div>

        {/* Notes */}
        <div>
          <label htmlFor="notes" className="block text-sm text-dark-400 mb-1">
            Notes
          </label>
          <textarea id="notes" {...register('notes')} className="input" rows={2} placeholder="Notes internes..." />
        </div>

        {/* Lines (creation only) */}
        {!isEdit && (
          <div className="border-t border-dark-600 pt-4">
            {hasLinenProduct && isEventTooSoon && (
              <div className="mb-4 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-start gap-2 text-amber-400 text-sm">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>
                  <strong>Délai insuffisant pour le linge (NAPPES)</strong> — Les réservations incluant du linge
                  nécessitent un délai minimum de 90 jours avant l'événement.
                </span>
              </div>
            )}
            <div className="flex items-center justify-between mb-4">
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

            {watchedDeliveryDate && watchedReturnDate && (
              <p className="text-xs text-dark-500 mb-2">
                Durée : <span className="text-dark-300 font-medium">{rentalDays} jour{rentalDays > 1 ? 's' : ''}</span>
                {' '}({watchedDeliveryDate} → {watchedReturnDate})
              </p>
            )}

            <div className="space-y-2">
              {lines.map((line, index) => {
                const product = getProductPrice(line.product_id)
                return (
                  <div key={index} className="flex flex-col sm:flex-row sm:items-center gap-2">
                    <select
                      value={line.product_id}
                      onChange={(e) => updateLine(index, 'product_id', Number(e.target.value))}
                      className="input w-full sm:flex-1"
                    >
                      <option value={0}>-- Produit --</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({formatCurrency(p.price_per_day_cents / 100)}/j)
                        </option>
                      ))}
                    </select>
                    {line.product_id > 0 && (
                      <VariantSelect
                        productId={line.product_id}
                        value={line.variant_id}
                        onChange={(v) => updateLine(index, 'variant_id', v)}
                      />
                    )}
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min={1}
                        value={line.quantity}
                        onChange={(e) => updateLine(index, 'quantity', Number(e.target.value))}
                        className="input w-20"
                      />
                      {product && (
                        <span className="text-sm text-dark-400 w-28 text-right whitespace-nowrap">
                          {formatCurrency((product.price_per_day_cents / 100) * line.quantity * rentalDays)}
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => removeLine(index)}
                        className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-dark-600 rounded text-dark-400 hover:text-red-500"
                        aria-label="Supprimer la ligne"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>

            {lines.some((l) => l.product_id > 0) && (() => {
              const total = lines.reduce((sum, l) => {
                const p = getProductPrice(l.product_id)
                return p ? sum + (p.price_per_day_cents / 100) * l.quantity * rentalDays : sum
              }, 0)
              return (
                <div className="flex justify-end mt-2 pt-2 border-t border-dark-600">
                  <span className="text-sm text-dark-400 mr-2">Total estimé :</span>
                  <span className="text-sm font-medium">{formatCurrency(total)}</span>
                </div>
              )
            })()}
          </div>
        )}

        {isEdit && (
          <div className="border-t border-dark-600 pt-4">
            <p className="text-sm text-dark-500">
              Les lignes de produits ne sont pas modifiables apres creation.
            </p>
          </div>
        )}
      </form>
    </Modal>
  )
}
