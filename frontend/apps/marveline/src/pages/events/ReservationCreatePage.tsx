import { PageHeader } from '@/components/PageHeader'
import { useState, useEffect } from 'react'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { normalizeError } from '@shared/errors/normalizer'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, X, AlertTriangle, ShoppingBag, ArrowLeft, Calendar, Users, MapPin, Truck, Package, CheckCircle2, Home } from 'lucide-react'
import { useCustomersList, useProductsList } from '@/api/queries'
import { useCreateReservation } from '@/api/queries'
import { useDeliveryZonesList } from '@/api/queries/useDeliveryZones'
import { useCarrierQuotes } from '@/api/queries/useCarrierQuotes'
import type { CarrierQuote } from '@/types/carrier'
import { useDebounce } from '@/hooks/useDebounce'
import { CataloguePickerModal, type CataloguePickerLine } from '@/components/catalogue/CataloguePickerModal'
import { ActionError } from '@shared/components/ui/ActionError'
import { ComboboxAsync } from '@shared/components/ui/ComboboxAsync'
import type { ReservationCreate } from '@/types/reservation'
import { formatCents } from '@/lib/utils'
import { Link } from '@tanstack/react-router'
import { VariantSelect } from '@/components/catalogue/VariantSelect'

const EVENT_TYPES: { value: 'mariage' | 'anniversaire' | 'entreprise' | 'autre'; label: string }[] = [
  { value: 'mariage', label: 'Mariage' },
  { value: 'anniversaire', label: 'Anniversaire' },
  { value: 'entreprise', label: 'Événement entreprise' },
  { value: 'autre', label: 'Autre' },
]

const reservationSchema = z.object({
  customer_id: z.number().min(1, 'Sélectionnez un client'),
  event_date: z.string().min(1, 'Date événement requise'),
  delivery_date: z.string().min(1, 'Date livraison requise'),
  return_date: z.string().min(1, 'Date retour requise'),
  event_location: z.string().optional(),
  event_type: z.enum(['mariage', 'anniversaire', 'entreprise', 'autre']).optional(),
  event_name: z.string().optional(),
  guest_count: z.number().nullable().optional(),
  notes: z.string().optional(),
  delivery_zone_id: z.number().nullable().optional(),
  delivery_method: z.enum(['self', 'carrier', 'pickup']).nullable().optional(),
  delivery_instructions: z.string().optional(),
  delivery_address: z.string().optional(),
  delivery_city: z.string().optional(),
  delivery_postal_code: z.string().optional(),
})

type FormData = z.infer<typeof reservationSchema>

interface LineItem {
  product_id?: number
  bundle_id?: number
  variant_id?: number
  product_name: string
  product_sku: string
  price_per_day_cents: number
  quantity: number
}

export default function ReservationCreatePage() {
  const navigate = useNavigate()
  const { customer_id: preselectedCustomerId } = useSearch({ strict: false }) as { customer_id?: number }
  const [lines, setLines] = useState<LineItem[]>([])
  const [linesError, setLinesError] = useState<string | null>(null)
  const [customerSearch, setCustomerSearch] = useState('')
  const debouncedCustomerSearch = useDebounce(customerSearch, 300)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [selectedQuote, setSelectedQuote] = useState<CarrierQuote | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<FormData, unknown, FormData>({
    resolver: zodResolver(reservationSchema),
    defaultValues: {
      customer_id: 0,
      event_date: '',
      delivery_date: '',
      return_date: '',
      event_location: '',
      event_type: undefined,
      event_name: '',
      guest_count: null,
      notes: '',
      delivery_zone_id: null,
      delivery_method: null,
      delivery_instructions: '',
      delivery_address: '',
      delivery_city: '',
      delivery_postal_code: '',
    },
  })

  // Pré-remplir le client si customer_id passé en search param (depuis fiche client)
  useEffect(() => {
    if (preselectedCustomerId && preselectedCustomerId > 0) {
      setValue('customer_id', preselectedCustomerId, { shouldValidate: true })
    }
  }, [preselectedCustomerId, setValue])

  const watchedDeliveryDate = watch('delivery_date')
  const watchedReturnDate = watch('return_date')
  const watchedEventDate = watch('event_date')

  const rentalDays = (() => {
    if (!watchedDeliveryDate || !watchedReturnDate) return 1
    const diff = (new Date(watchedReturnDate).getTime() - new Date(watchedDeliveryDate).getTime()) / 86400000
    return Math.max(1, Math.floor(diff) + 1)
  })()

  const { data: zonesData } = useDeliveryZonesList()
  const zones = zonesData ?? []
  const watchedDeliveryMethod = watch('delivery_method')
  const watchedZoneId = watch('delivery_zone_id')
  const selectedZone = zones.find((z) => z.id === watchedZoneId)

  // Auto-match zone tarifaire depuis le code postal (2 premiers chiffres = département)
  const watchedPostalCodeForZone = watch('delivery_postal_code')
  useEffect(() => {
    if (watchedDeliveryMethod !== 'self' || !watchedPostalCodeForZone || watchedPostalCodeForZone.length < 2) return
    const deptCode = watchedPostalCodeForZone.slice(0, 2)
    const matchedZone = zones.find((z) => z.department_code === deptCode && z.is_active)
    if (matchedZone && matchedZone.id !== watchedZoneId) {
      setValue('delivery_zone_id', matchedZone.id, { shouldValidate: true })
    }
  }, [watchedPostalCodeForZone, watchedDeliveryMethod, zones, watchedZoneId, setValue])

  const { data: customersData, isLoading: loadingCustomers } = useCustomersList({
    limit: 20,
    search_query: debouncedCustomerSearch || undefined,
  })
  const { data: productsData } = useProductsList({ limit: 1000, active_only: true })

  const customers = customersData?.items || []
  const products = productsData?.items || []
  const watchedCustomerId = watch('customer_id')
  const selectedCustomer = customers.find((c) => c.id === watchedCustomerId)
  const watchedPostalCode = watch('delivery_postal_code')

  // Poids total estimé (pour devis transporteur)
  const totalWeightGrams = lines.reduce((sum, l) => {
    if (!l.product_id) return sum
    const product = products.find((p) => p.id === l.product_id)
    return sum + (product?.weight_grams ?? 0) * l.quantity
  }, 0)

  // Devis transporteurs Boxtal
  const { data: carrierQuotes = [], isLoading: loadingQuotes } = useCarrierQuotes({
    weight_grams: totalWeightGrams || 1000,
    destination_postal_code: watchedPostalCode || '',
    enabled: watchedDeliveryMethod === 'carrier' && (watchedPostalCode?.length ?? 0) >= 2,
  })

  const createMutation = useCreateReservation()

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

  const totalLocationCents = lines.reduce((sum, l) => {
    return sum + l.price_per_day_cents * l.quantity * rentalDays
  }, 0)

  // Supplément dimanche : si la date de livraison tombe un dimanche
  const isSundayDelivery = (() => {
    if (!watchedDeliveryDate) return false
    return new Date(watchedDeliveryDate).getDay() === 0
  })()

  const deliveryFeeCents = watchedDeliveryMethod === 'pickup'
    ? 0
    : watchedDeliveryMethod === 'carrier' && selectedQuote
      ? selectedQuote.price_cents
      : (selectedZone?.delivery_fee_cents ?? 0)
        + (isSundayDelivery && selectedZone?.sunday_surcharge_cents ? selectedZone.sunday_surcharge_cents : 0)
  const totalEstimeCents = totalLocationCents + deliveryFeeCents

  const onSubmit = (data: FormData) => {
    const validLines = lines
      .filter((l) => (l.product_id || l.bundle_id) && l.quantity > 0)
      .map((l) => l.bundle_id
        ? { bundle_id: l.bundle_id, quantity: l.quantity }
        : { product_id: l.product_id!, quantity: l.quantity, variant_id: l.variant_id }
      )

    if (validLines.length === 0) {
      setLinesError('Ajoutez au moins un produit à la réservation.')
      return
    }
    const missingVariant = validLines.some((l) => 'product_id' in l && !l.variant_id)
    if (missingVariant) {
      setLinesError('Sélectionnez une variante pour chaque produit.')
      return
    }
    setLinesError(null)

    const createData: ReservationCreate = {
      customer_id: data.customer_id,
      event_date: data.event_date,
      delivery_date: data.delivery_date,
      return_date: data.return_date,
      event_location: data.event_location || undefined,
      event_type: data.event_type || undefined,
      event_name: data.event_name || undefined,
      guest_count: data.guest_count ?? undefined,
      notes: data.notes || undefined,
      lines: validLines,
      // Livraison
      delivery_zone_id: data.delivery_zone_id || undefined,
      delivery_method: data.delivery_method || undefined,
      delivery_fee_cents: deliveryFeeCents || undefined,
      delivery_instructions: data.delivery_instructions || undefined,
      carrier_name: selectedQuote?.carrier_name || undefined,
      carrier_code: selectedQuote?.carrier_code || undefined,
      // Adresse structurée
      delivery_address: data.delivery_address || undefined,
      delivery_city: data.delivery_city || undefined,
      delivery_postal_code: data.delivery_postal_code || undefined,
    }
    createMutation.mutate(createData, {
      onSuccess: () => navigate({ to: '/reservations' }),
    })
  }

  const addProductFromCatalogue = (line: CataloguePickerLine) => {
    setLinesError(null)
    const existing = lines.findIndex((l) =>
      line.bundle_id ? l.bundle_id === line.bundle_id : l.product_id === line.product_id
    )
    if (existing >= 0) {
      const updated = [...lines]
      updated[existing].quantity += line.quantity
      setLines(updated)
    } else {
      const product = line.product_id ? products.find((p) => p.id === line.product_id) : undefined
      setLines([
        ...lines,
        {
          product_id: line.product_id,
          bundle_id: line.bundle_id,
          product_name: line.product_name,
          product_sku: product?.sku ?? '',
          price_per_day_cents: line.unit_price_cents,
          quantity: line.quantity,
        },
      ])
    }
    setPickerOpen(false)
  }

  const removeLine = (index: number) => {
    setLines(lines.filter((_, i) => i !== index))
  }

  const updateLineQty = (index: number, quantity: number) => {
    const updated = [...lines]
    updated[index].quantity = Math.max(1, quantity)
    setLines(updated)
  }

  const error = createMutation.error

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/reservations" aria-label="Retour aux réservations" className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-dark-900 rounded-lg text-dark-400 hover:text-dark-50 transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <PageHeader title="Nouvelle réservation" subtitle="Créer une réservation avec sélection catalogue" />
      </div>

      <ActionError
        message={(error ? normalizeError(error).message || 'Une erreur est survenue' : null)}
        onDismiss={() => createMutation.reset()}
      />

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Colonne principale */}
          <div className="lg:col-span-2 space-y-6">
            {/* Section client */}
            <div className="card p-6 space-y-4">
              <h2 className="text-base font-semibold flex items-center gap-2">
                <Users className="w-4 h-4 text-primary-400" />
                Client
              </h2>
              <div>
                <ComboboxAsync
                  value={watch('customer_id') || ''}
                  onChange={(id) => setValue('customer_id', id as number, { shouldValidate: true })}
                  items={customers.map((c) => ({
                    id: c.id,
                    label: `${c.display_name} (${c.email})`,
                  }))}
                  onSearchChange={setCustomerSearch}
                  isLoading={loadingCustomers}
                  placeholder="Rechercher un client…"
                  className="mb-1"
                />
                {errors.customer_id && (
                  <p className="text-red-500 text-sm mt-1">{errors.customer_id.message}</p>
                )}
              </div>
            </div>

            {/* Section dates */}
            <div className="card p-6 space-y-4">
              <h2 className="text-base font-semibold flex items-center gap-2">
                <Calendar className="w-4 h-4 text-primary-400" />
                Dates
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label htmlFor="event_date" className="block text-sm text-dark-400 mb-1">Événement *</label>
                  <input id="event_date" {...register('event_date')} type="date" className="input" />
                  {errors.event_date && <p className="text-red-500 text-sm mt-1">{errors.event_date.message}</p>}
                </div>
                <div>
                  <label htmlFor="delivery_date" className="block text-sm text-dark-400 mb-1">Livraison *</label>
                  <input id="delivery_date" {...register('delivery_date')} type="date" className="input" />
                  {errors.delivery_date && <p className="text-red-500 text-sm mt-1">{errors.delivery_date.message}</p>}
                </div>
                <div>
                  <label htmlFor="return_date" className="block text-sm text-dark-400 mb-1">Retour *</label>
                  <input id="return_date" {...register('return_date')} type="date" className="input" />
                  {errors.return_date && <p className="text-red-500 text-sm mt-1">{errors.return_date.message}</p>}
                </div>
              </div>
              {watchedDeliveryDate && watchedReturnDate && (
                <p className="text-xs text-dark-500">
                  Durée location :{' '}
                  <span className="text-dark-300 font-medium">
                    {rentalDays} jour{rentalDays > 1 ? 's' : ''}
                  </span>{' '}
                  ({watchedDeliveryDate} → {watchedReturnDate})
                </p>
              )}
            </div>

            {/* Section événement */}
            <div className="card p-6 space-y-4">
              <h2 className="text-base font-semibold flex items-center gap-2">
                <MapPin className="w-4 h-4 text-primary-400" />
                Détails événement
              </h2>
              <div>
                <label htmlFor="event_location" className="block text-sm text-dark-400 mb-1">Lieu</label>
                <input
                  id="event_location"
                  {...register('event_location')}
                  type="text"
                  className="input"
                  placeholder="Adresse ou nom du lieu"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label htmlFor="event_type" className="block text-sm text-dark-400 mb-1">Type</label>
                  <select id="event_type" {...register('event_type')} className="input">
                    <option value="">-- Sélectionner --</option>
                    {EVENT_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="event_name" className="block text-sm text-dark-400 mb-1">Nom</label>
                  <input
                    id="event_name"
                    {...register('event_name')}
                    type="text"
                    className="input"
                    placeholder="ex: Mariage Dupont"
                  />
                </div>
                <div>
                  <label htmlFor="guest_count" className="block text-sm text-dark-400 mb-1">Invités</label>
                  <input
                    id="guest_count"
                    {...register('guest_count', { valueAsNumber: true })}
                    type="number"
                    min={1}
                    className="input"
                    placeholder="ex: 120"
                  />
                </div>
              </div>
              <div>
                <label htmlFor="notes" className="block text-sm text-dark-400 mb-1">Notes</label>
                <textarea id="notes" {...register('notes')} className="input" rows={3} placeholder="Notes internes…" />
              </div>
            </div>

            {/* Section livraison */}
            <div className="card p-6 space-y-5">
              <h2 className="text-base font-semibold flex items-center gap-2">
                <Truck className="w-4 h-4 text-primary-400" />
                Livraison
              </h2>

              {/* Méthode — cards sélectionnables */}
              <input type="hidden" {...register('delivery_method', { setValueAs: (v) => v === '' ? null : v })} />
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {([
                  { value: 'self', label: 'Livraison propre', icon: Truck, desc: 'Notre équipe livre' },
                  { value: 'carrier', label: 'Transporteur', icon: Package, desc: 'Via prestataire' },
                  { value: 'pickup', label: 'Retrait client', icon: Users, desc: 'Le client récupère' },
                ] as const).map((opt) => {
                  const active = watchedDeliveryMethod === opt.value
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => {
                        setValue('delivery_method', active ? null : opt.value, { shouldValidate: true })
                        setSelectedQuote(null)
                      }}
                      className={`relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all min-h-[44px] ${
                        active
                          ? 'border-primary-500 bg-primary-500/10'
                          : 'border-dark-700 bg-dark-900/40 hover:border-dark-500'
                      }`}
                    >
                      {active && (
                        <CheckCircle2 className="absolute top-2 right-2 w-4 h-4 text-primary-400" />
                      )}
                      <opt.icon className={`w-5 h-5 ${active ? 'text-primary-400' : 'text-dark-400'}`} />
                      <span className={`text-sm font-medium ${active ? 'text-white' : 'text-dark-300'}`}>
                        {opt.label}
                      </span>
                      <span className="text-[11px] text-dark-500">{opt.desc}</span>
                    </button>
                  )
                })}
              </div>

              {/* Adresse de livraison structurée — visible si self ou carrier */}
              {(watchedDeliveryMethod === 'self' || watchedDeliveryMethod === 'carrier') && (
                <div className="space-y-4">
                  {/* Pré-remplissage rapide (self) */}
                  {watchedDeliveryMethod === 'self' && selectedCustomer && (
                    <div className="space-y-2">
                      <p className="text-xs text-dark-500 font-medium uppercase tracking-wide">Pré-remplir depuis</p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {selectedCustomer.address && (
                          <button
                            type="button"
                            onClick={() => {
                              setValue('delivery_address', selectedCustomer.address || '', { shouldValidate: true })
                              setValue('delivery_city', selectedCustomer.city || '', { shouldValidate: true })
                              setValue('delivery_postal_code', selectedCustomer.postal_code || '', { shouldValidate: true })
                            }}
                            className="flex items-start gap-3 p-3 rounded-lg border border-dark-700 hover:border-primary-500 bg-dark-900/40 transition-all text-left min-h-[44px]"
                          >
                            <Home className="w-4 h-4 text-primary-400 mt-0.5 shrink-0" />
                            <div className="text-sm">
                              <p className="text-dark-300 font-medium">Adresse client</p>
                              <p className="text-dark-500 text-xs truncate">{selectedCustomer.address}</p>
                              {selectedCustomer.postal_code && (
                                <p className="text-dark-500 text-xs">{selectedCustomer.postal_code} {selectedCustomer.city}</p>
                              )}
                            </div>
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            setValue('delivery_address', '', { shouldValidate: true })
                            setValue('delivery_city', '', { shouldValidate: true })
                            setValue('delivery_postal_code', '', { shouldValidate: true })
                          }}
                          className="flex items-start gap-3 p-3 rounded-lg border border-dark-700 hover:border-primary-500 bg-dark-900/40 transition-all text-left min-h-[44px]"
                        >
                          <MapPin className="w-4 h-4 text-primary-400 mt-0.5 shrink-0" />
                          <div className="text-sm">
                            <p className="text-dark-300 font-medium">Autre adresse</p>
                            <p className="text-dark-500 text-xs">Saisir manuellement</p>
                          </div>
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Champs adresse structurée */}
                  <div>
                    <label htmlFor="delivery_address" className="block text-sm text-dark-400 mb-1">Adresse</label>
                    <input
                      id="delivery_address"
                      {...register('delivery_address')}
                      type="text"
                      className="input"
                      placeholder="Rue, numéro, complément"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label htmlFor="delivery_postal_code" className="block text-sm text-dark-400 mb-1">Code postal</label>
                      <input
                        id="delivery_postal_code"
                        {...register('delivery_postal_code')}
                        type="text"
                        className="input"
                        placeholder="60000"
                        maxLength={10}
                      />
                    </div>
                    <div>
                      <label htmlFor="delivery_city" className="block text-sm text-dark-400 mb-1">Ville</label>
                      <input
                        id="delivery_city"
                        {...register('delivery_city')}
                        type="text"
                        className="input"
                        placeholder="Beauvais"
                      />
                    </div>
                  </div>

                  {/* Zone de livraison — seulement en mode "self" */}
                  {watchedDeliveryMethod === 'self' && (
                    <>
                      <div>
                        <label htmlFor="delivery_zone_id" className="block text-sm text-dark-400 mb-1">Zone tarifaire</label>
                        <select
                          id="delivery_zone_id"
                          {...register('delivery_zone_id', { setValueAs: (v) => v === '' || v === 0 ? null : Number(v) })}
                          className="input"
                        >
                          <option value="">-- Sélectionner --</option>
                          {zones.filter((z) => z.is_active).map((z) => (
                            <option key={z.id} value={z.id}>
                              {z.department_name} ({z.department_code})
                              {z.delivery_fee_cents > 0 ? ` — ${formatCents(z.delivery_fee_cents)}` : ' — Sur devis'}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Feedback zone sélectionnée */}
                      {selectedZone && (
                        <div className="flex items-center gap-3 bg-dark-900/60 rounded-lg p-3">
                          <MapPin className="w-4 h-4 text-primary-400 shrink-0" />
                          <div className="text-sm">
                            <span className="text-dark-300">{selectedZone.department_name}</span>
                            {selectedZone.delivery_fee_cents > 0 ? (
                              <span className="ml-2 text-white font-medium">{formatCents(selectedZone.delivery_fee_cents)}</span>
                            ) : (
                              <span className="ml-2 text-amber-400">Sur devis</span>
                            )}
                            {isSundayDelivery && selectedZone.sunday_surcharge_cents > 0 && (
                              <span className="ml-2 text-amber-400 text-xs font-medium">
                                +{formatCents(selectedZone.sunday_surcharge_cents)} (dimanche)
                              </span>
                            )}
                            {!isSundayDelivery && selectedZone.sunday_surcharge_cents > 0 && (
                              <span className="ml-2 text-dark-500 text-xs">
                                (+{formatCents(selectedZone.sunday_surcharge_cents)} le dimanche)
                              </span>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Alerte zone non couverte */}
                      {watchedPostalCodeForZone && watchedPostalCodeForZone.length >= 2 && !selectedZone && zones.length > 0 && (
                        <div className="flex items-center gap-3 bg-amber-900/20 border border-amber-700/40 rounded-lg p-3">
                          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                          <p className="text-xs text-amber-300">
                            Aucune zone tarifaire pour le département {watchedPostalCodeForZone.slice(0, 2)} — tarif sur devis.
                          </p>
                        </div>
                      )}
                    </>
                  )}

                  {/* Devis transporteurs Boxtal */}
                  {watchedDeliveryMethod === 'carrier' && (
                    <div className="space-y-3">
                      <p className="text-xs text-dark-500 font-medium uppercase tracking-wide">Devis transporteurs</p>

                      {!watchedPostalCode || watchedPostalCode.length < 2 ? (
                        <p className="text-xs text-dark-500 bg-dark-900/40 rounded-lg px-3 py-2">
                          Saisissez le code postal de destination pour obtenir des devis.
                        </p>
                      ) : loadingQuotes ? (
                        <div className="flex items-center gap-2 text-sm text-dark-400 py-2">
                          <div className="w-4 h-4 border-2 border-primary-400 border-t-transparent rounded-full animate-spin" />
                          Recherche des tarifs...
                        </div>
                      ) : carrierQuotes.length > 0 ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {carrierQuotes.slice(0, 6).map((quote) => {
                            const isSelected = selectedQuote?.carrier_code === quote.carrier_code
                              && selectedQuote?.service_name === quote.service_name
                            return (
                              <button
                                key={`${quote.carrier_code}-${quote.service_name}`}
                                type="button"
                                onClick={() => setSelectedQuote(isSelected ? null : quote)}
                                className={`flex items-center justify-between p-3 rounded-lg border-2 transition-all text-left min-h-[44px] ${
                                  isSelected
                                    ? 'border-primary-500 bg-primary-500/10'
                                    : 'border-dark-700 bg-dark-900/40 hover:border-dark-500'
                                }`}
                              >
                                <div>
                                  <p className={`text-sm font-medium ${isSelected ? 'text-white' : 'text-dark-300'}`}>
                                    {quote.carrier_name}
                                  </p>
                                  <p className="text-xs text-dark-500">{quote.service_name}</p>
                                </div>
                                <div className="text-right">
                                  <p className={`text-sm font-semibold ${isSelected ? 'text-primary-400' : 'text-white'}`}>
                                    {formatCents(quote.price_cents)}
                                  </p>
                                  {quote.delivery_days && (
                                    <p className="text-xs text-dark-500">{quote.delivery_days}j</p>
                                  )}
                                </div>
                              </button>
                            )
                          })}
                        </div>
                      ) : (
                        <p className="text-xs text-amber-400 bg-amber-500/10 rounded-lg px-3 py-2">
                          Aucun devis disponible. Vous pouvez saisir les frais manuellement dans le champ ci-dessous.
                        </p>
                      )}

                      {totalWeightGrams > 0 && (
                        <p className="text-xs text-dark-500">
                          Poids total estimé : {(totalWeightGrams / 1000).toFixed(1)} kg
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}

              {watchedDeliveryMethod === 'pickup' && (
                <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/20 rounded-lg p-3 text-sm text-green-400">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  Retrait client — pas de frais de livraison
                </div>
              )}

              {/* Instructions — masquées si retrait */}
              {watchedDeliveryMethod && watchedDeliveryMethod !== 'pickup' && (
                <div>
                  <label htmlFor="delivery_instructions" className="block text-sm text-dark-400 mb-1">
                    Instructions de livraison
                  </label>
                  <textarea
                    id="delivery_instructions"
                    {...register('delivery_instructions')}
                    className="input"
                    rows={2}
                    placeholder="Accès, horaires, contact sur place..."
                  />
                </div>
              )}
            </div>

            {/* Section produits */}
            <div className="card p-6 space-y-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-base font-semibold flex items-center gap-2">
                  <ShoppingBag className="w-4 h-4 text-primary-400" />
                  Produits
                  {lines.length > 0 && (
                    <span className="ml-1 text-xs bg-primary-600 text-white rounded-full px-2 py-0.5">
                      {lines.length}
                    </span>
                  )}
                </h2>
                <button
                  type="button"
                  onClick={() => setPickerOpen(true)}
                  className="btn-primary btn-sm flex items-center gap-1"
                >
                  <Plus className="w-3 h-3" />
                  Ajouter du catalogue
                </button>
              </div>

              {hasLinenProduct && isEventTooSoon && (
                <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-start gap-2 text-amber-400 text-sm">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                  <span>
                    <strong>Délai insuffisant pour le linge (NAPPES)</strong> — Les réservations incluant du linge
                    nécessitent un délai minimum de 90 jours avant l'événement.
                  </span>
                </div>
              )}

              {linesError && (
                <p className="text-red-400 text-sm mb-2">{linesError}</p>
              )}
              {lines.length === 0 ? (
                <div className="text-center py-10 border border-dashed border-dark-600 rounded-xl">
                  <ShoppingBag className="w-10 h-10 text-dark-600 mx-auto mb-2" />
                  <p className="text-dark-400 text-sm">Aucun produit ajouté</p>
                  <button
                    type="button"
                    onClick={() => setPickerOpen(true)}
                    className="mt-4 text-primary-400 hover:text-primary-300 text-sm underline"
                  >
                    Parcourir le catalogue
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="grid grid-cols-12 gap-2 text-xs text-dark-500 px-1 mb-1">
                    <div className="col-span-5">Produit</div>
                    <div className="col-span-2 text-center">Qté</div>
                    <div className="col-span-2 text-right">Prix/j</div>
                    <div className="col-span-2 text-right">Sous-total</div>
                    <div className="col-span-1" />
                  </div>
                  {lines.map((line, index) => (
                    <div
                      key={index}
                      className="grid grid-cols-12 gap-2 items-center bg-dark-900/40 rounded-lg px-4 py-2"
                    >
                      <div className="col-span-5">
                        <p className="text-sm font-medium truncate">{line.product_name}</p>
                        <div className="flex items-center gap-2">
                          <p className="text-xs text-dark-500 font-mono">{line.product_sku}</p>
                          {line.product_id && (
                            <VariantSelect
                              productId={line.product_id}
                              value={line.variant_id}
                              onChange={(vid) => {
                                const updated = [...lines]
                                updated[index].variant_id = vid
                                setLines(updated)
                              }}
                            />
                          )}
                        </div>
                      </div>
                      <div className="col-span-2 flex justify-center">
                        <input
                          type="number"
                          min={1}
                          value={line.quantity}
                          onChange={(e) => updateLineQty(index, Number(e.target.value))}
                          className="input w-16 text-center text-sm py-1"
                          aria-label={`Quantité pour ${line.product_name}`}
                        />
                      </div>
                      <div className="col-span-2 text-right text-sm text-dark-400">
                        {formatCents(line.price_per_day_cents)}/j
                      </div>
                      <div className="col-span-2 text-right text-sm font-medium">
                        {formatCents(line.price_per_day_cents * line.quantity * rentalDays)}
                      </div>
                      <div className="col-span-1 flex justify-end">
                        <button
                          type="button"
                          onClick={() => removeLine(index)}
                          className="p-1 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-dark-600 rounded text-dark-400 hover:text-red-500"
                          aria-label="Supprimer la ligne"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Colonne récapitulatif */}
          <div className="space-y-4">
            <div className="card p-6 space-y-4 sticky top-4">
              <h2 className="text-base font-semibold">Récapitulatif</h2>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between text-dark-400">
                  <span>Lignes</span>
                  <span>{lines.length}</span>
                </div>
                <div className="flex justify-between text-dark-400">
                  <span>Durée</span>
                  <span>{rentalDays} j</span>
                </div>
                <div className="flex justify-between text-dark-400">
                  <span>Location</span>
                  <span>{formatCents(totalLocationCents)}</span>
                </div>
                {deliveryFeeCents > 0 && (
                  <div className="flex justify-between text-dark-400">
                    <span>Livraison</span>
                    <span>{formatCents(deliveryFeeCents)}</span>
                  </div>
                )}
                {watchedDeliveryMethod === 'carrier' && !selectedQuote && (
                  <div className="flex justify-between text-dark-500 text-xs">
                    <span>Livraison</span>
                    <span>Sélectionnez un transporteur</span>
                  </div>
                )}
                {selectedQuote && (
                  <div className="flex justify-between text-dark-400 text-xs">
                    <span>{selectedQuote.carrier_name}</span>
                    <span>{formatCents(selectedQuote.price_cents)}</span>
                  </div>
                )}
                <div className="border-t border-dark-600 pt-2 flex justify-between font-semibold">
                  <span>Total estimé</span>
                  <span className="text-primary-400">{formatCents(totalEstimeCents)}</span>
                </div>
              </div>

              <button
                type="submit"
                disabled={createMutation.isPending}
                className="btn-primary w-full"
              >
                {createMutation.isPending ? 'Création…' : 'Créer la réservation'}
              </button>

              <Link
                to="/reservations"
                className="btn-secondary w-full text-center block"
              >
                Annuler
              </Link>
            </div>
          </div>
        </div>
      </form>

      <CataloguePickerModal
        isOpen={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={addProductFromCatalogue}
      />
    </div>
  )
}
