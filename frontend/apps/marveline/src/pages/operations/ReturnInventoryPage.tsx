import { PageHeader } from '@/components/PageHeader'
import { useState, useMemo } from 'react'
import { useParams, useNavigate, Link } from '@tanstack/react-router'
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  RotateCcw,
  Package,
  Layers,
  ClipboardCheck,
  FileText,
} from 'lucide-react'
import { useReturnInventory, useSubmitReturn } from '@/api/queries/useOperations'
import { useToast } from '@/hooks'
import { useCreateDamageInvoice } from '@/api/queries/useInvoices'
import { Button, Progress } from '@shared/components/ui'
import { SignaturePad } from '@shared/components/ui/SignaturePad'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { DamageDeclarationModal } from './components/DamageDeclarationModal'
import type { ItemCondition, DamageDeclaration, ReturnCheckItem } from '@/types/operations'
import { cn, formatCents, formatDate } from '@/lib/utils'
import { normalizeError } from '@shared/errors/normalizer'

// ── Condition options ────────────────────────────────────────────────────────

const CONDITION_OPTIONS: { value: ItemCondition; label: string; color: string; bg: string }[] = [
  { value: 'new', label: 'Neuf', color: 'text-green-400', bg: 'bg-green-900/40 border-green-700/40' },
  { value: 'good', label: 'Bon état', color: 'text-green-400', bg: 'bg-green-900/30 border-green-700/30' },
  { value: 'fair', label: 'Correct', color: 'text-yellow-400', bg: 'bg-yellow-900/30 border-yellow-700/30' },
  { value: 'damaged', label: 'Endommagé', color: 'text-red-400', bg: 'bg-red-900/30 border-red-700/30' },
  { value: 'missing', label: 'Manquant', color: 'text-red-500', bg: 'bg-red-900/40 border-red-700/40' },
]

// ── Item state ───────────────────────────────────────────────────────────────

type ItemState = {
  quantity_returned: number
  condition: ItemCondition
  damages: DamageDeclaration[]
}

// ── Bundle grouping ──────────────────────────────────────────────────────────

interface BundleGroup {
  bundle_id: number
  bundle_name: string
  items: ReturnCheckItem[]
}

function groupByBundle(items: ReturnCheckItem[]): (ReturnCheckItem | BundleGroup)[] {
  const result: (ReturnCheckItem | BundleGroup)[] = []
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

function isBundleGroup(entry: ReturnCheckItem | BundleGroup): entry is BundleGroup {
  return 'items' in entry && 'bundle_id' in entry && !('line_id' in entry)
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6 animate-pulse">
      <div className="flex items-center gap-4">
        <div className="w-9 h-9 skel rounded-lg" />
        <div className="space-y-2 flex-1">
          <div className="h-5 skel rounded w-48" />
          <div className="h-3 skel rounded w-32" />
        </div>
      </div>
      <div className="h-2 skel rounded-full" />
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="card p-4 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="h-4 skel rounded w-40" />
            <div className="h-5 w-16 skel rounded-full" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="h-9 skel rounded" />
            <div className="h-9 skel rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Condition chip ────────────────────────────────────────────────────────────

function ConditionChip({ condition }: { condition: ItemCondition }) {
  const opt = CONDITION_OPTIONS.find((o) => o.value === condition)
  if (!opt) return null
  return (
    <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium border', opt.bg, opt.color)}>
      {opt.label}
    </span>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ReturnInventoryPage() {
  const { reservationId } = useParams({ strict: false }) as { reservationId: string }
  const navigate = useNavigate()
  const parsedReservationId = Number.parseInt(reservationId ?? '', 10)
  const resId = Number.isInteger(parsedReservationId) && parsedReservationId > 0 ? parsedReservationId : null

  const { data, isLoading, isError, refetch } = useReturnInventory(resId)
  const submitReturn = useSubmitReturn()
  const toast = useToast()
  const createDamageInvoice = useCreateDamageInvoice()

  const [itemStates, setItemStates] = useState<Record<string, ItemState>>({})
  const [collapsedBundles, setCollapsedBundles] = useState<Set<number>>(new Set())
  const [damageModalOpen, setDamageModalOpen] = useState(false)
  const [signature, setSignature] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [damageInvoiceError, setDamageInvoiceError] = useState<string | null>(null)

  const grouped = useMemo(() => groupByBundle(data?.items ?? []), [data])

  const toggleBundle = (bundleId: number) => {
    setCollapsedBundles((prev) => {
      const next = new Set(prev)
      if (next.has(bundleId)) next.delete(bundleId)
      else next.add(bundleId)
      return next
    })
  }

  // ── Products list (pour modale dommages) ──────────────────────────────────
  const products = useMemo(
    () => (data?.items ?? []).map((i) => ({ id: i.product_id, name: i.product_name ?? `Produit #${i.product_id}` })),
    [data],
  )

  const itemKey = (item: ReturnCheckItem) => `${item.line_id}-${item.product_id}`

  const getItemState = (item: ReturnCheckItem): ItemState =>
    itemStates[itemKey(item)] ?? {
      quantity_returned: item.quantity_returned ?? item.quantity_expected,
      condition: item.condition ?? 'good',
      damages: item.damages ?? [],
    }

  const updateItem = (item: ReturnCheckItem, patch: Partial<ItemState>) => {
    const key = itemKey(item)
    setItemStates((prev) => {
      const base = prev[key] ?? { quantity_returned: item.quantity_expected, condition: 'good' as ItemCondition, damages: [] }
      return { ...prev, [key]: { ...base, ...patch } }
    })
  }

  // ── KPI ──────────────────────────────────────────────────────────────────
  const kpi = useMemo(() => {
    const items = data?.items ?? []
    const total = items.length
    const checked = items.filter((item) => {
      const s = getItemState(item)
      return s.quantity_returned > 0
    }).length
    const damaged = Object.values(itemStates).filter((s) => s.condition === 'damaged' || s.condition === 'missing').length
    const totalDamageCost = Object.values(itemStates).reduce(
      (sum, s) => sum + s.damages.reduce((ds, d) => ds + (d.estimated_cost_cents ?? 0), 0),
      0,
    )
    return { total, checked, damaged, totalDamageCost }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, itemStates])

  const hasDamages = kpi.totalDamageCost > 0 || kpi.damaged > 0
  const allChecked = kpi.total > 0 && kpi.checked === kpi.total
  const damageInvoiceCharges = useMemo(() => {
    if (!data) return []

    return data.items.flatMap((item) => {
      const state = getItemState(item)
      const productName = item.product_name ?? `Produit #${item.product_id}`

      return state.damages
        .filter((d) => d.description.trim().length > 0 && (d.estimated_cost_cents ?? 0) > 0)
        .map((d) => ({
          charge_type: 'DAMAGE' as const,
          description: `${productName} - ${d.description.trim()}`.slice(0, 500),
          amount_cents: d.estimated_cost_cents as number,
        }))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, itemStates])

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleDamageAdded = (damage: { productId: number; description: string; severity: string; estimatedCostCents: number }) => {
    const item = (data?.items ?? []).find((i) => i.product_id === damage.productId)
    if (!item) return
    const state = getItemState(item)
    const newDamage: DamageDeclaration = {
      product_id: damage.productId,
      product_name: products.find((p) => p.id === damage.productId)?.name ?? '',
      category: 'other',
      severity: damage.severity as DamageDeclaration['severity'],
      description: damage.description,
      photo_urls: [],
      estimated_cost_cents: damage.estimatedCostCents,
      persisted: true,
    }
    updateItem(item, { damages: [...state.damages, newDamage], condition: 'damaged' })
  }

  const handleSubmit = () => {
    if (!data || resId == null) return
    setError(null)

    const items = (data.items ?? []).map((item) => {
      const s = getItemState(item)
      const newDamages = s.damages.filter((d) => !d.persisted)
      return {
        line_id: item.line_id,
        quantity_returned: s.quantity_returned,
        condition: s.condition,
        damages: newDamages.map((d) => ({
          damage_type_name: d.category,
          description: d.description,
          fee_cents: d.estimated_cost_cents ?? 0,
          photo_urls: d.photo_urls,
        })),
      }
    })

    submitReturn.mutate(
      { reservationId: resId, items, signatureUrl: signature ?? undefined },
      {
        onSuccess: (response) => {
          // D — Warning solde non réglé (non bloquant). L'opérateur peut générer
          // une facture de solde plus tard depuis la fiche résa.
          const balance = response?.balance_due_cents ?? 0
          if (balance > 0) {
            toast.warning(
              'Retour validé — solde restant',
              `Il reste ${(balance / 100).toFixed(2)} € à régler. Pensez à émettre une facture de solde.`,
            )
          } else {
            toast.success('Retour validé', 'Le matériel est bien revenu.')
          }
          navigate({ to: '/reservations/$id', params: { id: String(resId) } })
        },
        onError: (err) => {
          setError(normalizeError(err).message || 'Erreur lors de la validation du retour.')
        },
      },
    )
  }

  const handleCreateDamageInvoice = () => {
    if (!data || resId == null) return

    setDamageInvoiceError(null)
    if (damageInvoiceCharges.length === 0) {
      setDamageInvoiceError('Ajoutez un coût estimé (> 0) sur au moins un dommage pour facturer.')
      return
    }

    const notes = data.reference
      ? `Dommages constates au retour (${data.reference})`
      : `Dommages constates au retour (reservation #${resId})`

    createDamageInvoice.mutate(
      { reservation_id: resId, charges: damageInvoiceCharges, notes },
      {
        onSuccess: (invoice) => {
          navigate({ to: '/finance/invoices/$id', params: { id: String(invoice.id) } })
        },
        onError: (err) => {
          setDamageInvoiceError(normalizeError(err).message || 'Erreur lors de la creation de la facture dommage.')
        },
      },
    )
  }

  const handleBack = () => navigate({ to: '/reservations/$id', params: { id: String(resId) } })

  if (resId == null) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto py-12">
        <div className="card p-6 text-center text-red-400">
          Identifiant de réservation invalide.
        </div>
      </div>
    )
  }

  // ── Loading state ───────────────────────────────────────────────────────
  if (isLoading) return <Skeleton />

  // ── Error state ─────────────────────────────────────────────────────────
  if (isError) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto py-12">
        <ErrorState onRetry={() => refetch()} />
      </div>
    )
  }

  // ── Empty / not found ───────────────────────────────────────────────────
  if (!data || (data.items ?? []).length === 0) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={handleBack} aria-label="Retour">
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <PageHeader title="Retour matériel" />
        </div>
        <div className="text-center py-12 text-dark-400">
          <Package className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-sm font-medium">Aucun article à contrôler</p>
          <p className="text-xs mt-1">Cette réservation n'a pas d'articles en attente de retour.</p>
        </div>
      </div>
    )
  }

  // ── Progress variant ────────────────────────────────────────────────────
  const progressVariant = hasDamages ? 'warning' as const : allChecked ? 'success' as const : 'default' as const

  const renderItemCard = (item: ReturnCheckItem, indent = false) => {
    const s = getItemState(item)
    const key = itemKey(item)
    const missing = item.quantity_expected - s.quantity_returned
    const isDamaged = s.condition === 'damaged' || s.condition === 'missing'
    const isOk = s.quantity_returned === item.quantity_expected && !isDamaged

    return (
      <div
        key={key}
        className={cn(
          'card p-4 space-y-4 transition-colors',
          indent && 'ml-4 border-l-2 border-primary-500/20',
          isDamaged && 'ring-1 ring-red-700/40',
          isOk && 'ring-1 ring-green-700/30',
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <div className="w-10 h-10 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
              {item.image_url ? (
                <img src={item.image_url} alt={item.product_name ?? ''} className="w-full h-full object-cover" loading="lazy" />
              ) : (
                <Package className="w-4 h-4 text-dark-600" />
              )}
            </div>
            <div className="min-w-0">
              <p className="font-medium text-sm truncate">{item.product_name ?? `Produit #${item.product_id}`}</p>
              <div className="flex items-center gap-2 text-xs text-dark-400">
                <span>Attendu : {item.quantity_expected} · Retourné : {s.quantity_returned}</span>
                {item.sku && <span className="font-mono">{item.sku}</span>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <ConditionChip condition={s.condition} />
            {missing > 0 ? (
              <span className="text-red-400 text-xs font-medium">{missing} manquant{missing > 1 ? 's' : ''}</span>
            ) : (
              <CheckCircle className="w-4 h-4 text-green-400" />
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-dark-400 mb-1">Quantité retournée</label>
            <input
              type="number"
              min={0}
              max={item.quantity_expected}
              value={s.quantity_returned}
              onChange={(e) => updateItem(item, { quantity_returned: parseInt(e.target.value) || 0 })}
              className="input w-full"
            />
          </div>
          <div>
            <label className="block text-xs text-dark-400 mb-1">État constaté</label>
            <select
              value={s.condition}
              onChange={(e) => updateItem(item, { condition: e.target.value as ItemCondition })}
              className={cn('input w-full', CONDITION_OPTIONS.find((o) => o.value === s.condition)?.color)}
            >
              {CONDITION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Dommages listés */}
        {s.damages.length > 0 && (
          <div className="bg-red-900/10 border border-red-800/30 rounded-lg p-2.5 space-y-1">
            {s.damages.map((d, i) => (
              <p key={i} className="text-xs text-red-300 flex items-start gap-1.5">
                <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                <span>{d.description} ({d.severity}){d.estimated_cost_cents ? ` — ${formatCents(d.estimated_cost_cents)}` : ''}</span>
              </p>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={handleBack} aria-label="Retour">
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <RotateCcw className="w-5 h-5 text-amber-400 shrink-0" />
            <h1 className="text-xl font-semibold truncate">Retour matériel</h1>
            <span className="text-xs px-2 py-0.5 rounded-full font-medium border bg-orange-900/40 text-orange-300 border-orange-700/40">
              Contrôle
            </span>
          </div>
          <div className="flex items-center gap-2 text-sm text-dark-400 mt-0.5">
            {data.reference && <span>{data.reference}</span>}
            {data.customer_name && <span>· {data.customer_name}</span>}
            {data.return_date && <span>· Retour {formatDate(data.return_date)}</span>}
          </div>
        </div>
      </div>

      {/* Barre de progression */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs text-dark-400">
          <span className="flex items-center gap-1.5">
            <ClipboardCheck className="w-3.5 h-3.5" />
            {kpi.checked}/{kpi.total} articles vérifiés
          </span>
          {hasDamages && (
            <span className="text-red-400 font-medium">
              {kpi.damaged} endommagé{kpi.damaged > 1 ? 's' : ''}
            </span>
          )}
        </div>
        <Progress value={kpi.checked} max={kpi.total} variant={progressVariant} size="sm" />
      </div>

      {/* Résumé dommages */}
      {hasDamages && (
        <div className="flex items-center gap-4 bg-red-900/20 border border-red-700/40 rounded-xl p-4">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
          <div className="text-sm">
            <p className="text-red-300 font-medium">Dommages déclarés</p>
            <p className="text-red-400">
              {kpi.damaged} article{kpi.damaged > 1 ? 's' : ''} — Coût estimé : {formatCents(kpi.totalDamageCost)}
            </p>
          </div>
        </div>
      )}

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

          return renderItemCard(entry as ReturnCheckItem)
        })}
      </div>

      {/* Bouton déclarer dommage */}
      <Button
        variant="outline"
        className="w-full border-red-700/40 text-red-400 hover:text-red-300 hover:bg-red-900/20"
        onClick={() => setDamageModalOpen(true)}
        leftIcon={<AlertTriangle className="w-4 h-4" />}
      >
        Déclarer un dommage
      </Button>

      {/* Signature */}
      <div className="card p-4">
        <SignaturePad
          label="Signature responsable retour"
          onSign={(dataUrl) => setSignature(dataUrl)}
          onClear={() => setSignature(null)}
        />
      </div>

      {/* Erreur */}
      {error && (
        <div className="bg-red-900/20 border border-red-700 rounded-lg px-4 py-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Créer / Lier une facture */}
      {hasDamages ? (
        <div className="space-y-2">
          <Button
            variant="secondary"
            className="w-full"
            onClick={handleCreateDamageInvoice}
            disabled={damageInvoiceCharges.length === 0}
            loading={createDamageInvoice.isPending}
            leftIcon={<FileText className="w-4 h-4" />}
          >
            Créer une facture dommage
          </Button>
          {damageInvoiceCharges.length === 0 && (
            <p className="text-xs text-amber-400">
              Aucun dommage valorisé: renseignez un coût estimé pour générer la facture.
            </p>
          )}
          {damageInvoiceError && (
            <p className="text-xs text-red-400">{damageInvoiceError}</p>
          )}
        </div>
      ) : (
        <Link
          to="/finance/invoices/new"
          className="w-full flex items-center justify-center gap-2 btn-secondary py-4"
        >
          <FileText className="w-4 h-4" />
          Créer une facture
        </Link>
      )}

      {/* Lier à une facture existante */}
      <Link
        to="/finance/invoices"
        search={resId ? { reservation_id: resId } : {}}
        className="w-full flex items-center justify-center gap-2 btn-secondary text-sm min-h-[44px]"
      >
        <FileText className="w-4 h-4" />
        Lier à une facture existante
      </Link>

      {/* Valider */}
      <Button
        variant="primary"
        size="lg"
        className="w-full bg-amber-600 hover:bg-amber-700"
        onClick={handleSubmit}
        disabled={!allChecked}
        loading={submitReturn.isPending}
        leftIcon={<RotateCcw className="w-5 h-5" />}
      >
        Valider le retour
      </Button>

      <DamageDeclarationModal
        open={damageModalOpen}
        onClose={() => setDamageModalOpen(false)}
        reservationId={resId}
        products={products}
        onDeclared={handleDamageAdded}
      />
    </div>
  )
}
