import { PageHeader } from '@/components/PageHeader'
import { useState, useMemo, useEffect } from 'react'
import { useParams, useNavigate, Link } from '@tanstack/react-router'
import {
  AlertTriangle, ArrowLeft, CheckCircle, ChevronDown, ChevronRight,
  ClipboardCheck, Layers, Package, QrCode, Truck, Ban,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useDepartureInventory, useSubmitDeparture, useBlockDeparture } from '@/api/queries/useOperations'
import { QRScanner } from '@shared/components/ui/QRScanner'
import { SignaturePad } from '@shared/components/ui/SignaturePad'
import type { ItemCondition, DepartureCheckItem, DepartureInventory } from '@/types/operations'
import { normalizeError } from '@shared/errors/normalizer'
import { useOperationsStore } from '@/stores/operationsStore'

const CONDITION_OPTIONS: { value: ItemCondition; label: string }[] = [
  { value: 'new', label: 'Neuf' },
  { value: 'good', label: 'Bon état' },
  { value: 'fair', label: 'État correct' },
  { value: 'damaged', label: 'Endommagé' },
  { value: 'missing', label: 'Manquant' },
]

type ItemState = {
  quantity_loaded: number
  condition: ItemCondition
  qr_scanned: boolean
  scanned_codes: string[]
}

interface BundleGroup {
  bundle_id: number
  bundle_name: string
  items: DepartureCheckItem[]
}

function groupByBundle(items: DepartureCheckItem[]): (DepartureCheckItem | BundleGroup)[] {
  const result: (DepartureCheckItem | BundleGroup)[] = []
  const bundleMap = new Map<number, BundleGroup>()

  for (const item of items) {
    if (item.is_bundle_item && item.bundle_id) {
      let group = bundleMap.get(item.bundle_id)
      if (!group) {
        group = { bundle_id: item.bundle_id, bundle_name: item.bundle_name ?? 'Pack', items: [] }
        bundleMap.set(item.bundle_id, group)
        result.push(group)
      }
      group.items.push(item)
    } else {
      result.push(item)
    }
  }
  return result
}

function isBundleGroup(entry: DepartureCheckItem | BundleGroup): entry is BundleGroup {
  return 'items' in entry && 'bundle_id' in entry && !('line_id' in entry)
}

export default function DepartureInventoryPage() {
  const { reservationId } = useParams({ strict: false }) as { reservationId: string }
  const navigate = useNavigate()
  const resId = parseInt(reservationId, 10)

  const { data, isLoading } = useDepartureInventory(resId)
  const submitDeparture = useSubmitDeparture()
  const blockDeparture = useBlockDeparture()
  const { setDepartureInventory, setActiveReservationId } = useOperationsStore()

  // Sync store quand les donnees backend arrivent
  useEffect(() => {
    if (data) {
      setDepartureInventory(data as DepartureInventory)
      setActiveReservationId(resId)
    }
  }, [data, resId, setDepartureInventory, setActiveReservationId])

  const [itemStates, setItemStates] = useState<Record<string, ItemState>>({})
  const [blockReason, setBlockReason] = useState('')
  const [showBlockForm, setShowBlockForm] = useState(false)
  const [activeScanner, setActiveScanner] = useState<number | null>(null)
  const [signature, setSignature] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [collapsedBundles, setCollapsedBundles] = useState<Set<number>>(new Set())

  const grouped = useMemo(() => groupByBundle(data?.items ?? []), [data])

  const toggleBundle = (bundleId: number) => {
    setCollapsedBundles((prev) => {
      const next = new Set(prev)
      if (next.has(bundleId)) next.delete(bundleId)
      else next.add(bundleId)
      return next
    })
  }

  const getItemState = (item: DepartureCheckItem): ItemState =>
    itemStates[itemKey(item)] ?? {
      quantity_loaded: item.quantity_loaded ?? item.quantity_expected,
      condition: item.condition ?? 'good',
      qr_scanned: item.qr_scanned ?? false,
      scanned_codes: item.scanned_codes ?? [],
    }

  const itemKey = (item: DepartureCheckItem) => `${item.line_id}-${item.product_id}`

  const { updateDepartureItem } = useOperationsStore()

  const updateItem = (item: DepartureCheckItem, patch: Partial<ItemState>) => {
    const key = itemKey(item)
    setItemStates((prev) => ({
      ...prev,
      [key]: { ...getItemState(item), ...patch },
    }))
    // Sync vers le store pour partage avec ArticleCheckPage
    updateDepartureItem(item.line_id, patch as Partial<DepartureCheckItem>)
  }

  const handleScan = (item: DepartureCheckItem, value: string) => {
    const state = getItemState(item)
    if (!state.scanned_codes.includes(value)) {
      updateItem(item, {
        qr_scanned: true,
        scanned_codes: [...state.scanned_codes, value],
      })
    }
    setActiveScanner(null)
  }

  const handleSubmit = () => {
    if (!data) return
    setError(null)

    const items = (data.items ?? []).map((item) => {
      const s = getItemState(item)
      return {
        line_id: item.line_id,
        product_id: item.product_id,
        quantity_loaded: s.quantity_loaded,
        condition: s.condition,
        qr_scanned: s.qr_scanned,
        scanned_codes: s.scanned_codes,
      }
    })

    submitDeparture.mutate(
      { reservationId: resId, items, signatureUrl: signature ?? undefined },
      {
        onSuccess: () => navigate({ to: '/reservations/$id', params: { id: String(resId) } }),
        onError: (err) => {
          setError(normalizeError(err).message || 'Erreur lors de la validation du départ.')
        },
      }
    )
  }

  if (isLoading) return (
    <div className="space-y-4 animate-pulse">
      <div className="card p-6 space-y-4">
        <div className="h-4 skel rounded w-48" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center justify-between py-2 border-b border-dark-600">
            <div className="h-3 skel rounded w-40" />
            <div className="h-7 skel rounded w-24" />
          </div>
        ))}
      </div>
    </div>
  )
  if (!data) return <div className="p-6 text-center text-dark-400">Données introuvables.</div>

  const allChecked = (data.items ?? []).length > 0 && (data.items ?? []).every((item) => {
    const s = getItemState(item)
    return s.quantity_loaded > 0
  })

  const renderItemCard = (item: DepartureCheckItem, indent = false) => {
    const s = getItemState(item)
    const key = itemKey(item)
    return (
      <div key={key} className={cn('card space-y-4', indent && 'ml-4 border-l-2 border-primary-500/20')}>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <div className="w-10 h-10 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
              {item.image_url ? (
                <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" loading="lazy" />
              ) : (
                <Package className="w-4 h-4 text-dark-600" />
              )}
            </div>
            <div className="min-w-0">
              <p className="font-medium text-sm truncate">{item.product_name}</p>
              <div className="flex items-center gap-2 text-xs text-dark-400">
                <span>Attendu : {item.quantity_expected}</span>
                {item.sku && <span className="font-mono">{item.sku}</span>}
              </div>
            </div>
          </div>
          {s.qr_scanned && (
            <span className="flex items-center gap-1 text-green-400 text-xs shrink-0">
              <CheckCircle className="w-3.5 h-3.5" /> Scanné
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-dark-400 mb-1">Quantité chargée</label>
            <input
              type="number"
              min={0}
              value={s.quantity_loaded}
              onChange={(e) => updateItem(item, { quantity_loaded: parseInt(e.target.value) || 0 })}
              className="input"
            />
          </div>
          <div>
            <label className="block text-xs text-dark-400 mb-1">État</label>
            <select
              value={s.condition}
              onChange={(e) => updateItem(item, { condition: e.target.value as ItemCondition })}
              className="input"
            >
              {CONDITION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        <button
          onClick={() => setActiveScanner(activeScanner === key ? null : key)}
          className="flex items-center gap-2 text-sm text-dark-400 hover:text-gold-400"
        >
          <QrCode className="w-4 h-4" />
          {s.scanned_codes.length > 0
            ? `${s.scanned_codes.length} code(s) scanné(s)`
            : 'Scanner QR'}
        </button>

        {activeScanner === key && (
          <div className="rounded-lg overflow-hidden">
            <QRScanner
              active
              mode="scan"
              onScan={(v) => handleScan(item, v)}
              onError={() => setActiveScanner(null)}
            />
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate({ to: '/reservations' })}
          aria-label="Retour aux réservations"
          className="p-2 hover:bg-dark-600 rounded text-dark-400"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <div className="flex items-center gap-2">
            <Truck className="w-5 h-5 text-blue-400" />
            <PageHeader title="Pré-départ" subtitle={`${data.reference ?? `Réservation #${resId}`}${data.customer_name ? ` · ${data.customer_name}` : ''}`} />
          </div>

        </div>
      </div>

      {/* Hero statut départ */}
      <div className="card p-4 border bg-orange-900/20 border-orange-700/40">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            {data.reference && <p className="font-semibold text-sm">{data.reference}</p>}
            <p className="text-xs text-dark-400 mt-0.5">
              {data.checked_items ?? 0} / {data.total_items ?? (data.items ?? []).length} articles chargés
            </p>
          </div>
          <span className={cn(
            'text-xs px-2.5 py-1 rounded-full font-medium border',
            data.can_depart
              ? 'bg-green-900/40 text-green-300 border-green-700/40'
              : 'bg-orange-900/40 text-orange-300 border-orange-700/40',
          )}>
            {data.can_depart ? 'Départ autorisé' : 'En préparation'}
          </span>
        </div>
      </div>

      {/* Alerte blocage départ */}
      {!data.can_depart && (
        <div className="bg-red-900/20 border border-red-700/40 rounded-xl p-4 space-y-3">
          <div className="flex items-start gap-3">
            <Ban className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="text-sm flex-1">
              <p className="text-red-300 font-semibold">
                {data.departure_blocked_reason === 'deposit_required'
                  ? 'Depart bloque — Caution non encaissee'
                  : 'Depart bloque — Pre-verifications incompletes'}
              </p>
              <p className="text-red-400/80 text-xs mt-1">
                {data.departure_blocked_reason === 'deposit_required'
                  ? 'La caution doit etre encaissee avant de valider le depart.'
                  : 'Tous les elements de pre-check doivent etre coches avant le depart.'}
              </p>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap ml-8">
            {data.departure_blocked_reason === 'deposit_required' && (
              <Link
                to="/reservations/$id"
                params={{ id: String(resId) }}
                className="btn-primary btn-sm flex items-center gap-1.5 text-xs"
              >
                Collecter la caution
              </Link>
            )}
            <button
              onClick={() => navigate({ to: '/reservations/$id', params: { id: String(resId) } })}
              className="btn-secondary btn-sm text-xs"
            >
              Voir la reservation
            </button>
          </div>
        </div>
      )}

      {/* Boutons contrôle */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Link
          to="/operations/departure/$reservationId/check"
          params={{ reservationId }}
          search={{ index: 0 }}
          className="btn-secondary flex items-center justify-center gap-2 min-h-[44px] text-sm"
        >
          <ClipboardCheck className="w-4 h-4" />
          Article par article
        </Link>
        <Link
          to="/reservations/$id/legal"
          params={{ id: String(resId) }}
          className="btn-primary flex items-center justify-center gap-2 min-h-[44px] text-sm"
        >
          <ClipboardCheck className="w-4 h-4" />
          Contrôle légal
        </Link>
      </div>

      {/* Checklist articles (groupés par bundle) */}
      <div className="space-y-4">
        {grouped.map((entry) => {
          if (isBundleGroup(entry)) {
            const isCollapsed = collapsedBundles.has(entry.bundle_id)
            return (
              <div key={`bundle-${entry.bundle_id}`} className="space-y-2">
                {/* Header pack */}
                <button
                  type="button"
                  onClick={() => toggleBundle(entry.bundle_id)}
                  className="w-full card p-3 flex items-center gap-3 hover:bg-dark-700/30 transition-colors"
                >
                  <div className="w-10 h-10 rounded-lg bg-primary-500/10 flex items-center justify-center shrink-0">
                    <Layers className="w-5 h-5 text-primary-400" />
                  </div>
                  <div className="flex-1 min-w-0 text-left">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm truncate">{entry.bundle_name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-primary-500/15 text-primary-400 border border-primary-500/30 shrink-0">
                        Pack
                      </span>
                    </div>
                    <p className="text-xs text-dark-400">{entry.items.length} article{entry.items.length > 1 ? 's' : ''}</p>
                  </div>
                  {isCollapsed ? (
                    <ChevronRight className="w-4 h-4 text-dark-500 shrink-0" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-dark-500 shrink-0" />
                  )}
                </button>
                {/* Items du pack */}
                {!isCollapsed && (
                  <div className="space-y-2">
                    {entry.items.map((item) => renderItemCard(item, true))}
                  </div>
                )}
              </div>
            )
          }

          return renderItemCard(entry as DepartureCheckItem)
        })}
      </div>

      {/* Signature */}
      <div className="card">
        <SignaturePad
          label="Signature responsable départ"
          onSign={(dataUrl) => setSignature(dataUrl)}
          onClear={() => setSignature(null)}
        />
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-700 rounded-lg px-4 py-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Bloquer le départ */}
      {data.can_depart && (showBlockForm ? (
        <div className="card space-y-4">
          <p className="text-sm text-red-300 font-medium">Raison du blocage</p>
          <textarea
            rows={2}
            placeholder="Décrivez la raison du blocage…"
            value={blockReason}
            onChange={(e) => setBlockReason(e.target.value)}
            className="input"
          />
          <div className="flex gap-2">
            <button
              onClick={() => { setShowBlockForm(false); setBlockReason('') }}
              className="flex-1 text-sm text-dark-400 hover:text-dark-50 py-2 rounded-lg border border-dark-600"
            >
              Annuler
            </button>
            <button
              onClick={() => {
                if (!blockReason.trim()) return
                blockDeparture.mutate(
                  { reservationId: resId, reason: blockReason.trim() },
                  {
                    onSuccess: () => navigate({ to: '/reservations/$id', params: { id: String(resId) } }),
                    onError: (err) => setError(
                      normalizeError(err).message || 'Erreur lors du blocage.'
                    ),
                  }
                )
              }}
              disabled={!blockReason.trim() || blockDeparture.isPending}
              className="flex-1 flex items-center justify-center gap-2 bg-red-700 hover:bg-red-800 text-white text-sm font-medium py-2 rounded-lg disabled:opacity-50"
            >
              <Ban className="w-4 h-4" />
              {blockDeparture.isPending ? 'Blocage…' : 'Confirmer le blocage'}
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowBlockForm(true)}
          className="btn-danger w-full flex items-center justify-center gap-2"
        >
          <Ban className="w-4 h-4" />
          Bloquer le départ
        </button>
      ))}

      {/* Valider */}
      <button
        onClick={handleSubmit}
        disabled={!data.can_depart || submitDeparture.isPending}
        className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-4 rounded-xl disabled:opacity-50"
      >
        <Truck className="w-5 h-5" />
        {submitDeparture.isPending ? 'Validation…' : 'Valider le départ'}
      </button>
    </div>
  )
}
