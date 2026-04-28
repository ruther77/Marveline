import { useState, useEffect, useRef } from 'react'
import { Truck, Package, Users, CheckCircle2, MapPin, Home, AlertTriangle } from 'lucide-react'
import { useDeliveryZonesList } from '@/api/queries/useDeliveryZones'
import { useCarrierQuotes } from '@/api/queries/useCarrierQuotes'
import type { CarrierQuote } from '@/types/carrier'
import type { DevisDeliveryMethod } from '@/types/devis'
import { formatCents } from '@/lib/utils'

const DELIVERY_METHODS = [
  { value: 'self' as const, label: 'Livraison propre', icon: Truck, desc: 'Notre equipe livre' },
  { value: 'carrier' as const, label: 'Transporteur', icon: Package, desc: 'Via prestataire' },
  { value: 'pickup' as const, label: 'Retrait client', icon: Users, desc: 'Le client recupere' },
]

export interface DeliveryStepData {
  delivery_method: DevisDeliveryMethod | null
  delivery_fee_cents: number
  carrier_name: string | null
  carrier_code: string | null
  delivery_address: string
  delivery_city: string
  delivery_postal_code: string
  delivery_zone_id: number | null
  delivery_instructions: string
}

interface DevisDeliveryStepProps {
  value: DeliveryStepData
  onChange: (data: DeliveryStepData) => void
  totalWeightGrams: number
  customerAddress?: string | null
  customerCity?: string | null
  customerPostalCode?: string | null
  deliveryDate?: string | null
}

export function DevisDeliveryStep({
  value,
  onChange,
  totalWeightGrams,
  customerAddress,
  customerCity,
  customerPostalCode,
  deliveryDate,
}: DevisDeliveryStepProps) {
  const [selectedQuote, setSelectedQuote] = useState<CarrierQuote | null>(null)

  const { data: zonesData } = useDeliveryZonesList()
  const zones = zonesData ?? []

  const selectedZone = zones.find((z) => z.id === value.delivery_zone_id)

  // Ref fraîche pour éviter les closures stale dans les effects
  const valueRef = useRef(value)
  valueRef.current = value

  // Mode "self" — auto-match zone + fee en une seule mise à jour atomique
  // (évite la race condition entre deux effects distincts qui spreadent value stale)
  const isSundayDelivery = deliveryDate ? new Date(deliveryDate).getDay() === 0 : false

  useEffect(() => {
    if (value.delivery_method !== 'self') return
    const v = valueRef.current
    const deptCode = v.delivery_postal_code.slice(0, 2)
    const matched = v.delivery_postal_code.length >= 2
      ? zones.find((z) => z.department_code === deptCode && z.is_active)
      : null
    const newZoneId = matched?.id ?? null
    const newFee = matched
      ? matched.delivery_fee_cents + (isSundayDelivery && matched.sunday_surcharge_cents ? matched.sunday_surcharge_cents : 0)
      : 0
    if (newZoneId !== v.delivery_zone_id || newFee !== v.delivery_fee_cents) {
      onChange({ ...v, delivery_zone_id: newZoneId, delivery_fee_cents: newFee })
    }
  }, [value.delivery_postal_code, value.delivery_method, zones, isSundayDelivery])

  // Mode "carrier" — fee depuis le devis transporteur sélectionné
  useEffect(() => {
    if (value.delivery_method !== 'carrier') return
    const fee = selectedQuote?.price_cents ?? 0
    if (fee !== valueRef.current.delivery_fee_cents) {
      onChange({ ...valueRef.current, delivery_fee_cents: fee })
    }
  }, [value.delivery_method, selectedQuote])

  // Carrier quotes
  const { data: carrierQuotes = [], isLoading: loadingQuotes } = useCarrierQuotes({
    weight_grams: totalWeightGrams || 1000,
    destination_postal_code: value.delivery_postal_code || '',
    enabled: value.delivery_method === 'carrier' && (value.delivery_postal_code?.length ?? 0) >= 2,
  })

  const update = (partial: Partial<DeliveryStepData>) => onChange({ ...value, ...partial })

  const setMethod = (method: DevisDeliveryMethod | null) => {
    setSelectedQuote(null)
    update({
      delivery_method: method,
      carrier_name: null,
      carrier_code: null,
      delivery_fee_cents: 0,
      delivery_zone_id: null,
    })
  }

  const selectCarrierQuote = (quote: CarrierQuote | null) => {
    setSelectedQuote(quote)
    update({
      carrier_name: quote?.carrier_name ?? null,
      carrier_code: quote?.carrier_code ?? null,
      delivery_fee_cents: quote?.price_cents ?? 0,
    })
  }

  const prefillCustomerAddress = () => {
    update({
      delivery_address: customerAddress ?? '',
      delivery_city: customerCity ?? '',
      delivery_postal_code: customerPostalCode ?? '',
    })
  }

  const clearAddress = () => {
    update({
      delivery_address: '',
      delivery_city: '',
      delivery_postal_code: '',
    })
  }

  return (
    <div className="card space-y-5">
      <h2 className="text-base font-semibold flex items-center gap-2">
        <Truck className="w-4 h-4 text-primary-400" />
        Livraison
      </h2>

      {/* Method selection cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {DELIVERY_METHODS.map((opt) => {
          const active = value.delivery_method === opt.value
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => setMethod(active ? null : opt.value)}
              className={`relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all min-h-[44px] ${
                active
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-dark-700 bg-dark-900/40 hover:border-dark-500'
              }`}
            >
              {active && <CheckCircle2 className="absolute top-2 right-2 w-4 h-4 text-primary-400" />}
              <opt.icon className={`w-5 h-5 ${active ? 'text-primary-400' : 'text-dark-400'}`} />
              <span className={`text-sm font-medium ${active ? 'text-white' : 'text-dark-300'}`}>{opt.label}</span>
              <span className="text-[11px] text-dark-500">{opt.desc}</span>
            </button>
          )
        })}
      </div>

      {/* Address section — visible for self or carrier */}
      {(value.delivery_method === 'self' || value.delivery_method === 'carrier') && (
        <div className="space-y-4">
          {/* Quick prefill from customer */}
          {value.delivery_method === 'self' && customerAddress && (
            <div className="space-y-2">
              <p className="text-xs text-dark-500 font-medium uppercase tracking-wide">Pre-remplir depuis</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={prefillCustomerAddress}
                  className="flex items-start gap-3 p-3 rounded-lg border border-dark-700 hover:border-primary-500 bg-dark-900/40 transition-all text-left min-h-[44px]"
                >
                  <Home className="w-4 h-4 text-primary-400 mt-0.5 shrink-0" />
                  <div className="text-sm">
                    <p className="text-dark-300 font-medium">Adresse client</p>
                    <p className="text-dark-500 text-xs truncate">{customerAddress}</p>
                    {customerPostalCode && (
                      <p className="text-dark-500 text-xs">{customerPostalCode} {customerCity}</p>
                    )}
                  </div>
                </button>
                <button
                  type="button"
                  onClick={clearAddress}
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

          {/* Structured address fields */}
          <div>
            <label className="block text-sm text-dark-400 mb-1">Adresse</label>
            <input
              type="text"
              value={value.delivery_address}
              onChange={(e) => update({ delivery_address: e.target.value })}
              className="input"
              placeholder="Rue, numero, complement"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-dark-400 mb-1">Code postal</label>
              <input
                type="text"
                value={value.delivery_postal_code}
                onChange={(e) => update({ delivery_postal_code: e.target.value })}
                className="input"
                placeholder="60000"
                maxLength={10}
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">Ville</label>
              <input
                type="text"
                value={value.delivery_city}
                onChange={(e) => update({ delivery_city: e.target.value })}
                className="input"
                placeholder="Beauvais"
              />
            </div>
          </div>

          {/* Delivery zones — self only */}
          {value.delivery_method === 'self' && (
            <>
              <div>
                <label className="block text-sm text-dark-400 mb-1">Zone tarifaire</label>
                <select
                  value={value.delivery_zone_id ?? ''}
                  onChange={(e) => update({ delivery_zone_id: e.target.value ? Number(e.target.value) : null })}
                  className="input"
                >
                  <option value="">-- Selectionner --</option>
                  {zones.filter((z) => z.is_active).map((z) => (
                    <option key={z.id} value={z.id}>
                      {z.department_name} ({z.department_code})
                      {z.delivery_fee_cents > 0 ? ` — ${formatCents(z.delivery_fee_cents)}` : ' — Sur devis'}
                    </option>
                  ))}
                </select>
              </div>

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
                  </div>
                </div>
              )}

              {value.delivery_postal_code && value.delivery_postal_code.length >= 2 && !selectedZone && zones.length > 0 && (
                <div className="flex items-center gap-3 bg-amber-900/20 border border-amber-700/40 rounded-lg p-3">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <p className="text-xs text-amber-300">
                    Aucune zone tarifaire pour le departement {value.delivery_postal_code.slice(0, 2)} — tarif sur devis.
                  </p>
                </div>
              )}
            </>
          )}

          {/* Boxtal carrier quotes */}
          {value.delivery_method === 'carrier' && (
            <div className="space-y-3">
              <p className="text-xs text-dark-500 font-medium uppercase tracking-wide">Devis transporteurs</p>

              {!value.delivery_postal_code || value.delivery_postal_code.length < 2 ? (
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
                        onClick={() => selectCarrierQuote(isSelected ? null : quote)}
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
                  Aucun devis disponible pour ce code postal.
                </p>
              )}

              {totalWeightGrams > 0 && (
                <p className="text-xs text-dark-500">
                  Poids total estime : {(totalWeightGrams / 1000).toFixed(1)} kg
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Pickup confirmation */}
      {value.delivery_method === 'pickup' && (
        <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/20 rounded-lg p-3 text-sm text-green-400">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          Retrait client — pas de frais de livraison
        </div>
      )}

      {/* Instructions — hidden for pickup */}
      {value.delivery_method && value.delivery_method !== 'pickup' && (
        <div>
          <label className="block text-sm text-dark-400 mb-1">Instructions de livraison</label>
          <textarea
            value={value.delivery_instructions}
            onChange={(e) => update({ delivery_instructions: e.target.value })}
            className="input"
            rows={2}
            placeholder="Acces, horaires, contact sur place..."
          />
        </div>
      )}

      {/* Fee summary */}
      {value.delivery_method && value.delivery_fee_cents > 0 && (
        <div className="flex items-center justify-between bg-dark-900/40 rounded-lg px-4 py-3 border border-dark-700">
          <span className="text-sm text-dark-400">Frais de livraison</span>
          <span className="text-sm font-semibold text-gold-400">{formatCents(value.delivery_fee_cents)}</span>
        </div>
      )}
    </div>
  )
}
