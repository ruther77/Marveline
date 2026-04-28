import { PageHeader } from '@/components/PageHeader'
import { useState, useEffect } from 'react'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { ArrowLeft, ArrowRight, Save, Send, Loader2, Shield, Tag, CalendarDays } from 'lucide-react'
import { ActionError } from '@shared/components/ui/ActionError'
import { useCreateDevis } from '@/api/queries/useDevis'
import { normalizeError } from '@shared/errors/normalizer'
import { useCustomersList } from '@/api/queries'
import { useDebounce } from '@/hooks/useDebounce'
import { formatCents, formatDate } from '@/lib/utils'
import { DevisLineEditor } from './components/DevisLineEditor'
import type { DevisLineEditorLine } from './components/DevisLineEditor'
import { DevisDeliveryStep, type DeliveryStepData } from './components/DevisDeliveryStep'
import { useCartStore } from '@/stores/cartStore'
import { ComboboxAsync } from '@shared/components/ui/ComboboxAsync'

// ── SessionStorage persistence ────────────────────────────────────────────────

const DRAFT_KEY = 'devis_draft'

interface DevisDraft {
  customerId: number | ''
  eventDate: string
  validUntil: string
  eventLocation: string
  notes: string
  conditionsPaiement: string
  lines: DevisLineEditorLine[]
  messageAccompagnement: string
  delivery: DeliveryStepData
  cautionRequired: boolean
  cautionAmountEuros: string
  discountPct: string
  deliveryDate: string
  returnDate: string
}

const EMPTY_DELIVERY: DeliveryStepData = {
  delivery_method: null,
  delivery_fee_cents: 0,
  carrier_name: null,
  carrier_code: null,
  delivery_address: '',
  delivery_city: '',
  delivery_postal_code: '',
  delivery_zone_id: null,
  delivery_instructions: '',
}

function loadDraft(): DevisDraft | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function saveDraft(draft: DevisDraft) {
  try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft)) } catch {}
}

function clearDraft() {
  try { sessionStorage.removeItem(DRAFT_KEY) } catch {}
}

const CONDITIONS_PAIEMENT = [
  { value: '30_acompte', label: '30 % a la commande, solde avant evenement' },
  { value: '50_50', label: '50 % a la commande, 50 % a la livraison' },
  { value: 'comptant', label: 'Paiement comptant a la signature' },
  { value: 'fin_evenement', label: "Paiement integral en fin d'evenement" },
] as const

const STEP_LABELS = ['Client & Evenement', 'Articles', 'Livraison', 'Options', 'Recap & Envoi']

const DELIVERY_METHOD_LABELS: Record<string, string> = {
  self: 'Livraison propre',
  carrier: 'Transporteur',
  pickup: 'Retrait client',
}

const inDays = (n: number) => {
  const d = new Date()
  d.setDate(d.getDate() + n)
  return d.toISOString().split('T')[0]
}

type Step = 1 | 2 | 3 | 4 | 5

export default function DevisCreatePage() {
  const navigate = useNavigate()
  const { step: urlStep = 1 } = useSearch({ strict: false }) as { step: number }
  const step = Math.min(Math.max(urlStep || 1, 1), 5) as Step

  const setStep = (s: Step) =>
    navigate({ search: (prev: Record<string, unknown>) => ({ ...prev, step: s }) })

  const draft = useState(() => loadDraft())[0]
  const cartLines = useCartStore((s) => s.lines)
  const clearCart = useCartStore((s) => s.clearLines)

  // Step 1 — Client & event info
  const [customerId, setCustomerId] = useState<number | ''>(draft?.customerId ?? '')
  const [eventDate, setEventDate] = useState(draft?.eventDate ?? inDays(30))
  const [validUntil, setValidUntil] = useState(draft?.validUntil ?? inDays(14))
  const [eventLocation, setEventLocation] = useState(draft?.eventLocation ?? '')
  const [notes, setNotes] = useState(draft?.notes ?? '')
  const [conditionsPaiement, setConditionsPaiement] = useState(draft?.conditionsPaiement ?? '')

  // Step 2 — Lines (draft > cartStore > empty)
  const [lines, setLines] = useState<DevisLineEditorLine[]>(() =>
    draft?.lines?.length
      ? draft.lines
      : cartLines.map((l) => ({
          product_id: l.product_id,
          bundle_id: l.bundle_id,
          label: l.product_name,
          quantity: l.quantity,
          unit_price_cents: l.unit_price_cents,
        }))
  )

  // Step 3 — Delivery
  const [delivery, setDelivery] = useState<DeliveryStepData>(
    draft?.delivery ?? EMPTY_DELIVERY
  )

  // Step 4 — Options
  const [cautionRequired, setCautionRequired] = useState(draft?.cautionRequired ?? false)
  const [cautionAmountEuros, setCautionAmountEuros] = useState(draft?.cautionAmountEuros ?? '')
  const [discountPct, setDiscountPct] = useState(draft?.discountPct ?? '')
  const [deliveryDate, setDeliveryDate] = useState(draft?.deliveryDate ?? '')
  const [returnDate, setReturnDate] = useState(draft?.returnDate ?? '')

  // Step 5 — Recap + message
  const [messageAccompagnement, setMessageAccompagnement] = useState(draft?.messageAccompagnement ?? '')
  const [error, setError] = useState<string | null>(null)
  const [customerSearch, setCustomerSearch] = useState('')
  const debouncedCustomerSearch = useDebounce(customerSearch, 300)

  useEffect(() => {
    saveDraft({
      customerId, eventDate, validUntil, eventLocation,
      notes, conditionsPaiement, lines, messageAccompagnement, delivery,
      cautionRequired, cautionAmountEuros, discountPct, deliveryDate, returnDate,
    })
  }, [customerId, eventDate, validUntil, eventLocation, notes, conditionsPaiement,
      lines, messageAccompagnement, delivery, cautionRequired, cautionAmountEuros,
      discountPct, deliveryDate, returnDate])

  const createMutation = useCreateDevis()
  const { data: customersData, isLoading: loadingCustomers } = useCustomersList({
    limit: 20,
    search_query: debouncedCustomerSearch || undefined,
  })
  const customers = customersData?.items || []

  const canStep2 = customerId !== '' && eventDate && validUntil
  const canStep3 = lines.length > 0

  const totalWeightGrams = 0 // DevisLineEditorLine ne porte pas de poids

  // Totals — même ordre que le backend : remise sur articles, TVA, puis livraison
  const totalArticles = lines.reduce((s, l) => s + l.quantity * l.unit_price_cents, 0)
  const discountPctCentièmes = discountPct ? Math.round(parseFloat(discountPct) * 100) : 0
  const subtotalAfterDiscount = discountPctCentièmes > 0
    ? Math.round(totalArticles * (10000 - discountPctCentièmes) / 10000)
    : totalArticles
  const discountAmount = totalArticles - subtotalAfterDiscount
  const tvaDefaultCentièmes = 2000  // 20% par défaut (backend default)
  const tvaPreviewCents = Math.round(subtotalAfterDiscount * tvaDefaultCentièmes / 10000)
  const deliveryFeeCents = delivery.delivery_fee_cents || 0
  const totalFinal = subtotalAfterDiscount + tvaPreviewCents + deliveryFeeCents

  const buildPayload = () => ({
    customer_id: customerId as number,
    event_date: eventDate,
    valid_until: validUntil,
    event_location: eventLocation || undefined,
    notes: notes || undefined,
    conditions_paiement: conditionsPaiement || undefined,
    message_accompagnement: messageAccompagnement || undefined,
    lines: lines.map((l) => ({
      ...(l.product_id ? { product_id: l.product_id } : {}),
      ...(l.bundle_id ? { bundle_id: l.bundle_id } : {}),
      ...(l.variant_id ? { variant_id: l.variant_id } : {}),
      label: l.label,
      quantity: l.quantity,
      unit_price_cents: l.unit_price_cents,
    })),
    // Livraison
    delivery_method: delivery.delivery_method || undefined,
    delivery_fee_cents: delivery.delivery_fee_cents || undefined,
    carrier_name: delivery.carrier_name || undefined,
    carrier_code: delivery.carrier_code || undefined,
    delivery_address: delivery.delivery_address || undefined,
    delivery_city: delivery.delivery_city || undefined,
    delivery_postal_code: delivery.delivery_postal_code || undefined,
    delivery_zone_id: delivery.delivery_zone_id || undefined,
    delivery_instructions: delivery.delivery_instructions || undefined,
    // Options
    caution_required: cautionRequired || undefined,
    caution_amount_cents: cautionRequired && cautionAmountEuros
      ? Math.round(parseFloat(cautionAmountEuros) * 100)
      : undefined,
    discount_pct: discountPct ? Math.round(parseFloat(discountPct) * 100) : undefined,
    delivery_date: deliveryDate || undefined,
    return_date: returnDate || undefined,
  })

  const handleSubmit = (andSend = false) => {
    if (customerId === '') return
    setError(null)
    createMutation.mutate(buildPayload(), {
      onSuccess: (d) => {
        clearCart()
        clearDraft()
        if (andSend) {
          navigate({ to: '/devis/$id', params: { id: String(d.id) }, search: { send: '1' } })
        } else {
          navigate({ to: '/devis/$id', params: { id: String(d.id) } })
        }
      },
      onError: (err) => {
        setError(
          normalizeError(err).message || 'Erreur lors de la creation du devis.'
        )
      },
    })
  }

  const selectedCustomer = customers.find((c) => c.id === customerId)

  return (
    <div className="p-4 md:p-6 max-w-2xl lg:max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => {
            if (step === 1) { clearDraft(); navigate({ to: '/devis' }) }
            else setStep((step - 1) as Step)
          }}
          className="p-2 hover:bg-dark-600 rounded text-dark-400"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <PageHeader title="Nouveau devis" subtitle={`Etape ${step} / 5 — ${STEP_LABELS[step - 1]}`} />
      </div>

      {/* Stepper */}
      <div className="flex items-center">
        {[1, 2, 3, 4, 5].map((s) => (
          <div key={s} className="flex items-center flex-1 min-w-0">
            <div className="flex flex-col items-center gap-1 shrink-0">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold ${
                  s < step
                    ? 'bg-gold-500 text-dark-900'
                    : s === step
                    ? 'bg-gold-500/20 border border-gold-500 text-gold-400'
                    : 'bg-dark-900 text-dark-400'
                }`}
              >
                {s}
              </div>
              <span className={`text-[10px] leading-tight text-center hidden sm:block ${
                s === step ? 'text-gold-400 font-medium' : s < step ? 'text-dark-300' : 'text-dark-600'
              }`}>
                {STEP_LABELS[s - 1]}
              </span>
            </div>
            {s < 5 && <div className={`h-0.5 flex-1 mx-1 mb-4 sm:mb-0 ${s < step ? 'bg-gold-500' : 'bg-dark-900'}`} />}
          </div>
        ))}
      </div>

      {/* ── Step 1 — Client & Event ────────────────────────────────────────────── */}
      {step === 1 && (
        <div className="card space-y-4">
          <h2 className="font-medium">Informations generales</h2>

          <div>
            <label className="block text-sm text-dark-400 mb-1">Client *</label>
            <ComboboxAsync
              value={customerId}
              onChange={(id) => setCustomerId(id)}
              items={customers.map((c) => ({
                id: c.id,
                label: `${c.first_name} ${c.last_name}${c.company_name ? ` — ${c.company_name}` : ''}`,
              }))}
              onSearchChange={setCustomerSearch}
              isLoading={loadingCustomers}
              placeholder="Rechercher un client…"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">Date de l'evenement *</label>
              <input
                type="date"
                value={eventDate}
                onChange={(e) => setEventDate(e.target.value)}
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">Valide jusqu'au *</label>
              <input
                type="date"
                value={validUntil}
                onChange={(e) => setValidUntil(e.target.value)}
                className="input"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">Lieu de l'evenement</label>
            <input
              type="text"
              placeholder="Adresse, salle…"
              value={eventLocation}
              onChange={(e) => setEventLocation(e.target.value)}
              className="input"
            />
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">Conditions de paiement</label>
            <select
              value={conditionsPaiement}
              onChange={(e) => setConditionsPaiement(e.target.value)}
              className="input"
            >
              <option value="">Non specifiees</option>
              {CONDITIONS_PAIEMENT.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">Notes internes</label>
            <textarea
              rows={3}
              placeholder="Remarques, conditions particulieres…"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="input"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              disabled={!canStep2}
              title={!canStep2 ? "Selectionnez un client, une date d'evenement et une date de validite" : undefined}
              onClick={() => setStep(2)}
              className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm px-6 py-2 rounded-lg disabled:opacity-40"
            >
              Suivant <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ── Step 2 — Lines ────────────────────────────────────────────────────── */}
      {step === 2 && (
        <div className="space-y-4">
          <h2 className="font-medium">Articles du devis</h2>
          <DevisLineEditor lines={lines} onChange={setLines} />

          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="text-sm text-dark-400 hover:text-dark-50"
            >
              Retour
            </button>
            <button
              type="button"
              disabled={!canStep3}
              title={!canStep3 ? 'Ajoutez au moins un article au devis' : undefined}
              onClick={() => setStep(3)}
              className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm px-6 py-2 rounded-lg disabled:opacity-40"
            >
              Livraison <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ── Step 3 — Delivery ─────────────────────────────────────────────────── */}
      {step === 3 && (
        <div className="space-y-4">
          <DevisDeliveryStep
            value={delivery}
            onChange={setDelivery}
            totalWeightGrams={totalWeightGrams}
            customerAddress={selectedCustomer?.address}
            customerCity={selectedCustomer?.city}
            customerPostalCode={selectedCustomer?.postal_code}
            deliveryDate={eventDate}
          />

          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={() => setStep(2)}
              className="text-sm text-dark-400 hover:text-dark-50"
            >
              Retour
            </button>
            <button
              type="button"
              onClick={() => setStep(4)}
              className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm px-6 py-2 rounded-lg"
            >
              Options <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ── Step 4 — Options ──────────────────────────────────────────────────── */}
      {step === 4 && (
        <div className="space-y-4">
          {/* Caution */}
          <div className="card space-y-4">
            <div className="flex items-center gap-3">
              <Shield className="w-4 h-4 text-primary-400 shrink-0" />
              <h2 className="font-medium">Caution</h2>
            </div>

            <label className="flex items-center gap-3 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={cautionRequired}
                onChange={(e) => setCautionRequired(e.target.checked)}
                className="w-4 h-4 rounded accent-gold-500"
              />
              <span className="text-sm">Caution requise pour cet evenement</span>
            </label>

            {cautionRequired && (
              <div>
                <label className="block text-sm text-dark-400 mb-1">Montant de la caution (€)</label>
                <input
                  type="number"
                  min="0"
                  step="50"
                  placeholder="ex: 500"
                  value={cautionAmountEuros}
                  onChange={(e) => setCautionAmountEuros(e.target.value)}
                  className="input w-48"
                />
              </div>
            )}
          </div>

          {/* Remise */}
          <div className="card space-y-4">
            <div className="flex items-center gap-3">
              <Tag className="w-4 h-4 text-green-400 shrink-0" />
              <h2 className="font-medium">Remise commerciale</h2>
            </div>

            <div>
              <label className="block text-sm text-dark-400 mb-1">Remise (%)</label>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  placeholder="0"
                  value={discountPct}
                  onChange={(e) => setDiscountPct(e.target.value)}
                  className="input w-28"
                />
                {discountPct && parseFloat(discountPct) > 0 && (
                  <span className="text-sm text-green-400">
                    − {formatCents(discountAmount)} sur {formatCents(totalArticles)} HT
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Dates logistiques */}
          <div className="card space-y-4">
            <div className="flex items-center gap-3">
              <CalendarDays className="w-4 h-4 text-amber-400 shrink-0" />
              <div>
                <h2 className="font-medium">Dates logistiques</h2>
                <p className="text-xs text-dark-400 mt-0.5">Livraison et retour du materiel (facultatif)</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Livraison materiel</label>
                <input
                  type="date"
                  value={deliveryDate}
                  onChange={(e) => setDeliveryDate(e.target.value)}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">Retour materiel</label>
                <input
                  type="date"
                  value={returnDate}
                  onChange={(e) => setReturnDate(e.target.value)}
                  className="input"
                />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={() => setStep(3)}
              className="text-sm text-dark-400 hover:text-dark-50"
            >
              Retour
            </button>
            <button
              type="button"
              onClick={() => setStep(5)}
              className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm px-6 py-2 rounded-lg"
            >
              Recapitulatif <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ── Step 5 — Recap & Send ─────────────────────────────────────────────── */}
      {step === 5 && (
        <div className="space-y-4">
          <div className="card space-y-4">
            <h2 className="font-medium">Recapitulatif</h2>

            {/* Meta */}
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <span className="text-dark-400">Client</span>
              <span>
                {selectedCustomer
                  ? `${selectedCustomer.first_name} ${selectedCustomer.last_name}`
                  : '-'}
              </span>
              <span className="text-dark-400">Date evenement</span>
              <span>{formatDate(eventDate)}</span>
              <span className="text-dark-400">Validite</span>
              <span>jusqu'au {formatDate(validUntil)}</span>
              {eventLocation && (
                <>
                  <span className="text-dark-400">Lieu</span>
                  <span>{eventLocation}</span>
                </>
              )}
              {deliveryDate && (
                <>
                  <span className="text-dark-400">Livraison mat.</span>
                  <span>{formatDate(deliveryDate)}</span>
                </>
              )}
              {returnDate && (
                <>
                  <span className="text-dark-400">Retour mat.</span>
                  <span>{formatDate(returnDate)}</span>
                </>
              )}
            </div>

            {/* Lines */}
            <div className="border-t border-dark-600 pt-4 space-y-2">
              {lines.map((l, i) => (
                <div key={i} className="flex items-center justify-between text-sm py-1.5 px-3 rounded-lg bg-dark-900/30">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-dark-200 truncate">{l.label}</span>
                    {l.bundle_id && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-primary-500/15 text-primary-400 border border-primary-500/30 shrink-0">
                        Pack
                      </span>
                    )}
                    <span className="text-dark-500 shrink-0">x{l.quantity}</span>
                  </div>
                  <span className="font-medium shrink-0 ml-4">
                    {formatCents(l.quantity * l.unit_price_cents)}
                  </span>
                </div>
              ))}

              {/* Delivery line */}
              {delivery.delivery_method ? (
                <div className="flex items-center justify-between text-sm py-1.5 px-3 rounded-lg bg-primary-500/5 border border-primary-500/10">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-primary-400">
                      {DELIVERY_METHOD_LABELS[delivery.delivery_method] ?? delivery.delivery_method}
                    </span>
                    {delivery.carrier_name && (
                      <span className="text-dark-500 text-xs">({delivery.carrier_name})</span>
                    )}
                  </div>
                  <span className="font-medium shrink-0 ml-4 text-primary-400">
                    {delivery.delivery_fee_cents > 0 ? formatCents(delivery.delivery_fee_cents) : 'Inclus'}
                  </span>
                </div>
              ) : (
                <div className="text-sm py-1.5 px-3 rounded-lg bg-dark-900/30 text-dark-500 italic">
                  Aucune livraison selectionnee
                </div>
              )}

              {/* Totaux */}
              <div className="flex justify-between text-sm border-t border-dark-600 pt-3 mt-2 px-3">
                <span className="text-dark-400">Articles HT</span>
                <span>{formatCents(totalArticles)}</span>
              </div>
              {discountAmount > 0 && (
                <div className="flex justify-between text-sm px-3 text-green-400">
                  <span>Remise {discountPct}%</span>
                  <span>− {formatCents(discountAmount)}</span>
                </div>
              )}
              <div className="flex justify-between text-sm px-3 text-dark-400">
                <span>TVA 20%</span>
                <span>{formatCents(tvaPreviewCents)}</span>
              </div>
              {deliveryFeeCents > 0 && (
                <div className="flex justify-between text-sm px-3">
                  <span className="text-dark-400">Frais livraison</span>
                  <span>{formatCents(deliveryFeeCents)}</span>
                </div>
              )}
              <div className="flex justify-between text-sm font-semibold border-t border-dark-600 pt-3 mt-2 px-3">
                <span>Total TTC</span>
                <span className="text-gold-400 text-base">{formatCents(totalFinal)}</span>
              </div>
            </div>

            {/* Options recap */}
            {(cautionRequired || conditionsPaiement) && (
              <div className="border-t border-dark-600 pt-4 space-y-2 text-sm">
                {cautionRequired && cautionAmountEuros && (
                  <div className="flex justify-between">
                    <span className="text-dark-400">Caution</span>
                    <span className="text-primary-400">
                      {formatCents(Math.round(parseFloat(cautionAmountEuros) * 100))}
                    </span>
                  </div>
                )}
                {conditionsPaiement && (
                  <div className="flex items-start justify-between gap-4">
                    <span className="text-dark-400 shrink-0">Paiement</span>
                    <span className="text-dark-200 text-right">
                      {CONDITIONS_PAIEMENT.find((c) => c.value === conditionsPaiement)?.label}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Delivery address recap */}
            {delivery.delivery_method && delivery.delivery_method !== 'pickup' && delivery.delivery_address && (
              <div className="text-sm border-t border-dark-600 pt-4">
                <span className="text-dark-400">Adresse livraison : </span>
                <span className="text-dark-200">
                  {delivery.delivery_address}, {delivery.delivery_postal_code} {delivery.delivery_city}
                </span>
              </div>
            )}
          </div>

          <div className="card space-y-4">
            <h2 className="font-medium">Message d'accompagnement</h2>
            <textarea
              rows={4}
              placeholder="Message personnalise envoye avec le devis au client (optionnel)…"
              value={messageAccompagnement}
              onChange={(e) => setMessageAccompagnement(e.target.value)}
              className="input"
            />
          </div>

          <ActionError message={error} onDismiss={() => setError(null)} />

          <div className="flex items-center justify-between gap-4">
            <button
              type="button"
              onClick={() => setStep(4)}
              className="text-sm text-dark-400 hover:text-dark-50"
            >
              Retour
            </button>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handleSubmit(false)}
                disabled={createMutation.isPending}
                className="flex items-center gap-2 border border-dark-600 hover:border-dark-400 text-dark-200 font-medium text-sm px-4 py-2 rounded-lg disabled:opacity-60"
              >
                {createMutation.isPending
                  ? <Loader2 className="w-4 h-4 animate-spin" />
                  : <Save className="w-4 h-4" />}
                Brouillon
              </button>
              <button
                type="button"
                onClick={() => handleSubmit(true)}
                disabled={createMutation.isPending}
                className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-semibold text-sm px-6 py-2 rounded-lg disabled:opacity-60"
              >
                {createMutation.isPending
                  ? <Loader2 className="w-4 h-4 animate-spin" />
                  : <Send className="w-4 h-4" />}
                {createMutation.isPending ? 'Creation…' : 'Creer et envoyer'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
