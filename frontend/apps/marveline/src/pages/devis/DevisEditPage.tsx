import { PageHeader } from '@/components/PageHeader'
import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { useDevisDetail, useUpdateDevis } from '@/api/queries/useDevis'
import { normalizeError } from '@shared/errors/normalizer'
import { MoneyInput } from '@shared/components/ui'
import { formatCents, cn } from '@/lib/utils'
import { ArrowLeft, Plus, Trash2, Save, Package } from 'lucide-react'
import BundlePreviewPanel from './components/BundlePreviewPanel'
import { DevisDeliveryStep, type DeliveryStepData } from './components/DevisDeliveryStep'
import type { DevisCreate } from '@/types/devis'

interface EditLine {
  id?: number
  product_id?: number
  bundle_id?: number
  label: string
  quantity: number
  unit_price_cents: number
  weight_grams?: number | null
}

const EDITABLE_STATUSES = ['draft', 'version_pending']

export default function DevisEditPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const devisId = Number(id)

  const { data: devis, isLoading, error: loadError } = useDevisDetail(devisId)
  const updateMutation = useUpdateDevis()

  const [lines, setLines] = useState<EditLine[]>([])
  const [eventDate, setEventDate] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [eventLocation, setEventLocation] = useState('')
  const [notes, setNotes] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [delivery, setDelivery] = useState<DeliveryStepData>({
    delivery_method: null,
    delivery_fee_cents: 0,
    carrier_name: null,
    carrier_code: null,
    delivery_address: '',
    delivery_city: '',
    delivery_postal_code: '',
    delivery_zone_id: null,
    delivery_instructions: '',
  })

  useEffect(() => {
    if (!devis) return
    setLines(
      devis.lines.map(l => ({
        id: l.id,
        product_id: l.product_id,
        bundle_id: l.bundle_id,
        label: l.label,
        quantity: l.quantity,
        unit_price_cents: l.unit_price_cents,
        weight_grams: l.weight_grams,
      }))
    )
    setEventDate(devis.event_date?.slice(0, 10) ?? '')
    setValidUntil(devis.valid_until?.slice(0, 10) ?? '')
    setEventLocation(devis.event_location ?? '')
    setNotes(devis.notes ?? '')
    setDelivery({
      delivery_method: devis.delivery_method ?? null,
      delivery_fee_cents: devis.delivery_fee_cents ?? 0,
      carrier_name: devis.carrier_name ?? null,
      carrier_code: devis.carrier_code ?? null,
      delivery_address: devis.delivery_address ?? '',
      delivery_city: devis.delivery_city ?? '',
      delivery_postal_code: devis.delivery_postal_code ?? '',
      delivery_zone_id: devis.delivery_zone_id ?? null,
      delivery_instructions: devis.delivery_instructions ?? '',
    })
  }, [devis])

  // Track dirty state for unsaved changes warning
  const initialLoadDone = useRef(false)
  const [isDirty, setIsDirty] = useState(false)

  useEffect(() => {
    if (devis && !initialLoadDone.current) {
      initialLoadDone.current = true
    } else if (initialLoadDone.current) {
      setIsDirty(true)
    }
  }, [lines, eventDate, validUntil, eventLocation, notes, delivery])

  useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault() }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  const isReadOnly = devis ? !EDITABLE_STATUSES.includes(devis.status) : false
  const subtotalCents = lines.reduce((sum, l) => sum + l.quantity * l.unit_price_cents, 0)
  const tvaRateRaw = devis && 'tva_rate' in devis ? (devis as { tva_rate?: number }).tva_rate ?? 0 : 0
  const tvaRatePct = tvaRateRaw / 100  // 2000 → 20
  const tvaCents = Math.round((subtotalCents * tvaRateRaw) / 10000)
  const deliveryFeeCents = delivery.delivery_fee_cents || 0
  const totalCents = subtotalCents + tvaCents + deliveryFeeCents

  const addLine = () => {
    setLines(prev => [...prev, { label: '', quantity: 1, unit_price_cents: 0 }])
  }

  const removeLine = (index: number) => {
    setLines(prev => prev.filter((_, i) => i !== index))
  }

  const updateLine = (index: number, field: keyof EditLine, value: string | number) => {
    setLines(prev => prev.map((l, i) => (i === index ? { ...l, [field]: value } : l)))
  }

  const handleSave = async () => {
    setSaveError(null)
    setSaved(false)
    try {
      type DevisEditPayload = Omit<Partial<DevisCreate>, 'lines'> & {
        lines: Array<{
          id?: number
          product_id?: number
          bundle_id?: number
          label: string
          quantity: number
          unit_price_cents: number
        }>
      }

      const payload: DevisEditPayload = {
        event_date: eventDate,
        valid_until: validUntil,
        event_location: eventLocation || undefined,
        notes: notes || undefined,
        lines: lines.map(l => ({
          id: l.id,
          product_id: l.product_id,
          bundle_id: l.bundle_id,
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
      }
      await updateMutation.mutateAsync({ id: devisId, data: payload })
      setIsDirty(false)
      setSaved(true)
    } catch (err) {
      setSaveError(normalizeError(err).message || 'Erreur lors de la sauvegarde')
    }
  }

  // ── Loading skeleton ──────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <div className="h-8 w-52 skel rounded animate-pulse" />
        <div className="card p-6 space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-10 skel rounded animate-pulse" />
          ))}
        </div>
        <div className="card p-6 space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-10 skel rounded animate-pulse" />
          ))}
        </div>
        <div className="card p-6 space-y-2">
          <div className="h-6 w-40 skel rounded animate-pulse ml-auto" />
          <div className="h-8 w-32 skel rounded animate-pulse ml-auto" />
        </div>
      </div>
    )
  }

  // ── Error / not found ─────────────────────────────────────────────────────
  if (loadError || !devis) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="card p-8 text-center text-danger">
          {loadError ? normalizeError(loadError).message : 'Devis introuvable'}
        </div>
      </div>
    )
  }

  // ── Main view ─────────────────────────────────────────────────────────────
  return (
    <div className="max-w-3xl mx-auto space-y-4 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <Link
          to="/devis/$id"
          params={{ id: String(devisId) }}
          className="btn-secondary btn-sm flex items-center gap-2 min-h-[44px]"
        >
          <ArrowLeft className="w-4 h-4" />
          Retour
        </Link>
        <div className="flex-1 min-w-0">
          <PageHeader title="Modifier le devis" subtitle={`${devis.reference} — ${devis.customer_name}`} />
        </div>
        {isReadOnly && (
          <span className="text-xs font-medium px-2.5 py-1 rounded-lg bg-dark-900 text-dark-300">
            Non modifiable · {devis.status}
          </span>
        )}
      </div>

      {/* Informations générales */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">
          Informations
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">
              Date de l'événement
            </label>
            <input
              type="date"
              className="input w-full"
              value={eventDate}
              onChange={e => setEventDate(e.target.value)}
              disabled={isReadOnly}
            />
          </div>
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">
              Valide jusqu'au
            </label>
            <input
              type="date"
              className="input w-full"
              value={validUntil}
              onChange={e => setValidUntil(e.target.value)}
              disabled={isReadOnly}
            />
          </div>
        </div>
        <div>
          <label className="text-sm text-dark-400 mb-1.5 block">Lieu</label>
          <input
            className="input w-full"
            placeholder="Lieu de l'événement"
            value={eventLocation}
            onChange={e => setEventLocation(e.target.value)}
            disabled={isReadOnly}
          />
        </div>
        <div>
          <label className="text-sm text-dark-400 mb-1.5 block">
            Notes internes
          </label>
          <textarea
            className="input w-full min-h-[80px] resize-none"
            placeholder="Notes…"
            value={notes}
            onChange={e => setNotes(e.target.value)}
            disabled={isReadOnly}
          />
        </div>
      </div>

      {/* Lignes */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">
            Lignes
          </h2>
          {!isReadOnly && (
            <button
              onClick={addLine}
              className="btn-secondary btn-sm flex items-center gap-1.5 min-h-[44px]"
            >
              <Plus className="w-3.5 h-3.5" />
              Ajouter
            </button>
          )}
        </div>

        {/* Header colonnes */}
        {lines.length > 0 && (
          <div
            className={cn(
              'hidden sm:grid text-xs text-dark-400 px-1',
              isReadOnly ? 'grid-cols-[1fr_5rem_8rem_8rem]' : 'grid-cols-[1fr_5rem_8rem_8rem_2.5rem]'
            )}
          >
            <span>Description</span>
            <span className="text-center">Qté</span>
            <span className="text-right">Prix u. HT</span>
            <span className="text-right">Total HT</span>
          </div>
        )}

        {/* Empty state */}
        {lines.length === 0 && (
          <p className="text-sm text-dark-400 py-6 text-center">
            {isReadOnly ? 'Aucune ligne' : 'Aucune ligne — cliquez sur Ajouter'}
          </p>
        )}

        {/* Lignes éditables */}
        <div className="space-y-2">
          {lines.map((line, index) => (
            <div
              key={index}
              className="grid gap-2 items-center border-b border-dark-600 pb-2 last:border-0 last:pb-0
                         grid-cols-[1fr_5rem] sm:grid-cols-[1fr_5rem_8rem_8rem]"
              style={!isReadOnly ? { gridTemplateColumns: undefined } : undefined}
            >
              {/* Ligne mobile/desktop : label */}
              <input
                className="input text-sm col-span-2 sm:col-span-1"
                placeholder="Description"
                value={line.label}
                onChange={e => updateLine(index, 'label', e.target.value)}
                disabled={isReadOnly}
              />

              {/* Quantité */}
              <input
                type="number"
                className="input text-sm text-center"
                placeholder="Qté"
                min={1}
                value={line.quantity}
                onChange={e => updateLine(index, 'quantity', Math.max(1, Number(e.target.value)))}
                disabled={isReadOnly}
              />

              {/* Prix unitaire */}
              <MoneyInput
                value={line.unit_price_cents}
                onChange={v => updateLine(index, 'unit_price_cents', v)}
                disabled={isReadOnly}
              />

              {/* Sous-total */}
              <div className="text-right text-sm font-medium hidden sm:block">
                {formatCents(line.quantity * line.unit_price_cents)}
              </div>

              {/* Supprimer */}
              {!isReadOnly && (
                <button
                  onClick={() => removeLine(index)}
                  className="text-danger hover:bg-danger/10 p-2 rounded-lg transition-colors
                             min-h-[44px] min-w-[44px] flex items-center justify-center"
                  aria-label="Supprimer la ligne"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}

              {/* G31 : apercu bundle */}
              {line.bundle_id && (
                <div className="col-span-full">
                  <BundlePreviewPanel bundleId={line.bundle_id} className="mt-1" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Livraison */}
      {!isReadOnly && (
        <DevisDeliveryStep
          value={delivery}
          onChange={setDelivery}
          totalWeightGrams={lines.reduce((sum, l) => sum + l.quantity * (l.weight_grams || 0), 0)}
          deliveryDate={eventDate}
        />
      )}

      {/* Récapitulatif totaux */}
      <div className="card p-6 space-y-2">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide mb-4">
          Totaux
        </h2>
        <div className="flex justify-between text-sm">
          <span className="text-dark-400">Sous-total HT</span>
          <span>{formatCents(subtotalCents)}</span>
        </div>
        {tvaRatePct > 0 && (
          <div className="flex justify-between text-sm">
            <span className="text-dark-400">TVA ({tvaRatePct.toFixed(0)}%)</span>
            <span>{formatCents(tvaCents)}</span>
          </div>
        )}
        {deliveryFeeCents > 0 && (
          <div className="flex justify-between text-sm">
            <span className="text-dark-400">Frais livraison</span>
            <span>{formatCents(deliveryFeeCents)}</span>
          </div>
        )}
        <div className="flex justify-between font-semibold border-t border-dark-600 pt-2 mt-1">
          <span>Total TTC</span>
          <span className="text-primary-400">{formatCents(totalCents)}</span>
        </div>
      </div>

      {/* Actions */}
      {!isReadOnly && (
        <div className="flex items-center gap-4 justify-end flex-wrap">
          {saveError != null && (
            <p className="text-sm text-danger">{saveError}</p>
          )}
          {saved && (
            <p className="text-sm text-green-400">Sauvegardé ✓</p>
          )}
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="btn-primary flex items-center gap-2 min-h-[44px]"
          >
            {updateMutation.isPending ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Enregistrer
          </button>
        </div>
      )}
    </div>
  )
}
