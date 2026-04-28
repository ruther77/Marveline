import { useState, useMemo } from 'react'
import { useNavigate } from '@tanstack/react-router'
import {
  Wrench, Package, ChevronDown, ExternalLink,
  AlertTriangle, ArrowDownToLine, Plus, Pencil, Trash2,
} from 'lucide-react'
import { usePendingInspections, useMovementDetail } from '@/api/queries'
import {
  useDamageTypesList,
  useCreateDamageType,
  useUpdateDamageType,
  useDeleteDamageType,
} from '@/api/queries/useDamageTypes'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { normalizeError } from '@shared/errors/normalizer'
import { cn, formatDate, formatCents } from '@/lib/utils'
import type { InventoryMovementListItem, MovementStatus } from '@/types/inventory'
import type { DamageType } from '@/types/damage_type'

// ── Status chips ─────────────────────────────────────────────────────────────

const STATUS_CHIP: Record<string, { label: string; className: string }> = {
  scheduled:  { label: 'En attente', className: 'bg-yellow-900/40 text-yellow-300 border border-yellow-700/40' },
  in_transit: { label: 'À réparer',  className: 'bg-orange-900/40 text-orange-300 border border-orange-700/40' },
  completed:  { label: 'Clôturé',    className: 'bg-green-900/40 text-green-300 border border-green-700/40' },
}

function getChip(status: MovementStatus) {
  return STATUS_CHIP[status] ?? { label: status, className: 'bg-dark-900 text-dark-300' }
}

// ── Skeletons ────────────────────────────────────────────────────────────────

function KpiSkeleton() {
  return (
    <div className="card p-4 animate-pulse">
      <div className="h-2.5 bg-dark-700 rounded w-20 mb-2" />
      <div className="h-6 bg-dark-700 rounded w-10" />
    </div>
  )
}

function RowSkeleton() {
  return (
    <div className="flex items-center gap-4 p-4 animate-pulse">
      <div className="w-10 h-10 rounded-lg bg-dark-700 shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 bg-dark-700 rounded w-2/3" />
        <div className="h-2.5 bg-dark-700 rounded w-1/2" />
      </div>
      <div className="h-5 w-16 bg-dark-700 rounded-full" />
    </div>
  )
}

// ── Movement detail expansion ────────────────────────────────────────────────

function MovementExpansion({ movementId }: { movementId: number }) {
  const navigate = useNavigate()
  const { data: detail, isLoading, isError } = useMovementDetail(movementId)

  if (isLoading) {
    return (
      <div className="px-4 pb-4 animate-pulse space-y-2">
        <div className="h-3 bg-dark-700 rounded w-1/3" />
        <div className="h-3 bg-dark-700 rounded w-1/4" />
      </div>
    )
  }

  if (isError || !detail) {
    return (
      <div className="px-4 pb-4 text-xs text-red-400">
        Impossible de charger le détail du mouvement.
      </div>
    )
  }

  const products = detail.items
    .filter((item) => item.product_id)
    .map((item) => ({
      id: item.product_id!,
      name: item.product_name ?? `Produit #${item.product_id}`,
      quantity: item.quantity_expected,
      condition: item.condition,
    }))

  const uniqueProducts = Array.from(
    new Map(products.map((p) => [p.id, p])).values()
  )

  if (uniqueProducts.length === 0) {
    return (
      <div className="px-4 pb-4 text-xs text-dark-400">
        Aucun produit identifié dans ce mouvement.
      </div>
    )
  }

  return (
    <div className="px-4 pb-4 space-y-2">
      <p className="text-xs text-dark-400 font-medium">
        Produits concernés — cliquez pour planifier une maintenance
      </p>
      <div className="space-y-1">
        {uniqueProducts.map((p) => (
          <button
            key={p.id}
            onClick={() =>
              navigate({
                to: '/catalogue/products/$id/maintenance' as never,
                params: { id: String(p.id) } as never,
              })
            }
            className="flex items-center justify-between w-full px-4 py-2 rounded-lg bg-dark-900 hover:bg-dark-600 transition-colors text-left"
          >
            <div className="flex items-center gap-2 min-w-0">
              <Package className="w-3.5 h-3.5 text-dark-400 shrink-0" />
              <span className="text-sm truncate">{p.name}</span>
              <span className="text-xs text-dark-500">×{p.quantity}</span>
              {p.condition === 'damaged' && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-red-900/40 text-red-300 border border-red-700/40">
                  Endommagé
                </span>
              )}
            </div>
            <div className="flex items-center gap-1 text-primary-400 shrink-0">
              <Wrench className="w-3.5 h-3.5" />
              <span className="text-xs">Maintenance</span>
              <ExternalLink className="w-3 h-3" />
            </div>
          </button>
        ))}
      </div>

      {detail.inspection_notes && (
        <div className="text-xs text-dark-400 bg-dark-900/50 rounded p-2 mt-2">
          <span className="font-medium">Notes inspection :</span> {detail.inspection_notes}
        </div>
      )}

      {detail.damage_fee > 0 && (
        <p className="text-xs text-orange-400">
          Frais de dommage : {formatCents(detail.damage_fee)}
        </p>
      )}
    </div>
  )
}

// ── Damage Types inline section ─────────────────────────────────────────────

type DamageModal =
  | { type: 'none' }
  | { type: 'create' }
  | { type: 'edit'; item: DamageType }
  | { type: 'delete'; item: DamageType }

function DamageTypesSection() {
  const [modal, setModal] = useState<DamageModal>({ type: 'none' })
  const [formName, setFormName] = useState('')
  const [formFee, setFormFee] = useState('')
  const [formActive, setFormActive] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)

  const { data: damageTypesData, isLoading } = useDamageTypesList()
  const items = damageTypesData?.items ?? []
  const createMutation = useCreateDamageType()
  const updateMutation = useUpdateDamageType()
  const deleteMutation = useDeleteDamageType()

  const openCreate = () => {
    setFormName(''); setFormFee(''); setFormActive(true); setError(null)
    setModal({ type: 'create' })
  }

  const openEdit = (item: DamageType) => {
    setFormName(item.name)
    setFormFee(String(item.default_fee_cents / 100))
    setFormActive(item.is_active)
    setError(null)
    setModal({ type: 'edit', item })
  }

  const closeModal = () => { setModal({ type: 'none' }); setError(null) }

  const handleSubmit = () => {
    const feeCents = Math.round(parseFloat(formFee || '0') * 100)
    if (!formName.trim()) { setError('Le nom est requis'); return }
    if (isNaN(feeCents) || feeCents < 0) { setError('Montant invalide'); return }

    if (modal.type === 'create') {
      createMutation.mutate(
        { name: formName.trim(), default_fee_cents: feeCents },
        { onSuccess: closeModal, onError: (err) => setError(normalizeError(err).message || 'Erreur') },
      )
    } else if (modal.type === 'edit') {
      updateMutation.mutate(
        { id: modal.item.id, data: { name: formName.trim(), default_fee_cents: feeCents, is_active: formActive } },
        { onSuccess: closeModal, onError: (err) => setError(normalizeError(err).message || 'Erreur') },
      )
    }
  }

  const active = items.filter((i) => i.is_active)

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full text-left"
      >
        <h2 className="text-sm font-medium text-dark-300 flex items-center gap-1.5">
          <AlertTriangle className="w-4 h-4 text-red-400" />
          Types de dommages ({active.length})
        </h2>
        <ChevronDown className={cn('w-4 h-4 text-dark-500 transition-transform', expanded && 'rotate-180')} />
      </button>

      {expanded && (
        <div className="mt-3 space-y-2">
          {isLoading ? (
            <div className="card p-4 animate-pulse space-y-2">
              <div className="h-3 bg-dark-700 rounded w-36" />
              <div className="h-3 bg-dark-700 rounded w-24" />
            </div>
          ) : items.length === 0 ? (
            <p className="text-sm text-dark-500">Aucun type configuré</p>
          ) : (
            <div className="card p-0 divide-y divide-dark-600">
              {items.map((item) => (
                <div key={item.id} className={cn('flex items-center gap-4 px-4 py-3', !item.is_active && 'opacity-40')}>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{item.name}</p>
                    <p className="text-xs text-dark-400">
                      {item.default_fee_cents > 0 ? formatCents(item.default_fee_cents) : 'Montant libre'}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={() => openEdit(item)} className="p-1.5 rounded-lg hover:bg-dark-600 text-dark-400 hover:text-dark-50">
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => { setError(null); setModal({ type: 'delete', item }) }} className="p-1.5 rounded-lg hover:bg-dark-600 text-dark-400 hover:text-red-400">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <button onClick={openCreate} className="btn-secondary btn-sm flex items-center gap-1.5 text-xs">
            <Plus className="w-3.5 h-3.5" /> Nouveau type
          </button>
        </div>
      )}

      {/* Modal Créer / Modifier */}
      {(modal.type === 'create' || modal.type === 'edit') && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="modal-panel w-full max-w-md p-6 space-y-4">
            <h2 className="text-lg font-bold">
              {modal.type === 'create' ? 'Nouveau type de dommage' : 'Modifier le type'}
            </h2>
            {error && <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2">{error}</p>}
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Nom *</label>
                <input type="text" value={formName} onChange={(e) => setFormName(e.target.value)} className="input" placeholder="Casse, Rayure, Tache…" autoFocus />
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">Tarif par défaut (€)</label>
                <input type="number" value={formFee} onChange={(e) => setFormFee(e.target.value)} className="input" placeholder="0.00" min="0" step="0.01" />
                <p className="text-xs text-dark-500 mt-1">0 = montant à saisir manuellement</p>
              </div>
              {modal.type === 'edit' && (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={formActive} onChange={(e) => setFormActive(e.target.checked)} className="w-4 h-4 rounded" />
                  <span className="text-sm">Type actif</span>
                </label>
              )}
            </div>
            <div className="flex gap-4 pt-2">
              <button onClick={closeModal} className="btn-secondary flex-1">Annuler</button>
              <button onClick={handleSubmit} disabled={createMutation.isPending || updateMutation.isPending} className="btn-primary flex-1">
                {modal.type === 'create' ? 'Créer' : 'Enregistrer'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Supprimer */}
      {modal.type === 'delete' && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="modal-panel w-full max-w-md p-6 space-y-4">
            <h2 className="text-lg font-bold text-red-400">Supprimer le type</h2>
            <p className="text-sm text-dark-300">
              Supprimer <strong>«&nbsp;{modal.item.name}&nbsp;»</strong> ? Irréversible.
            </p>
            {error && <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2">{error}</p>}
            <div className="flex gap-4">
              <button onClick={closeModal} className="btn-secondary flex-1">Annuler</button>
              <button
                onClick={() => deleteMutation.mutate(modal.item.id, { onSuccess: closeModal, onError: (err) => setError(normalizeError(err).message || 'Erreur') })}
                disabled={deleteMutation.isPending}
                className="flex-1 py-2 rounded-xl bg-red-500 hover:bg-red-600 text-white font-medium transition-colors"
              >
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function RepairPlanningPage() {
  const navigate = useNavigate()
  const { data: inspections, isLoading, isError, refetch } = usePendingInspections()

  const [expandedId, setExpandedId] = useState<number | null>(null)

  const repairMovements = useMemo(
    () => (inspections ?? []).filter((m) => m.status === 'in_transit'),
    [inspections],
  )

  const pendingMovements = useMemo(
    () => (inspections ?? []).filter((m) => m.status === 'scheduled'),
    [inspections],
  )

  const kpi = useMemo(() => ({
    totalRepairs: repairMovements.length,
    totalArticles: repairMovements.reduce((s, m) => s + m.items_count, 0),
    totalPending: pendingMovements.length,
  }), [repairMovements, pendingMovements])

  const toggleExpand = (id: number) => {
    setExpandedId(expandedId === id ? null : id)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold flex items-center gap-2 min-w-0">
          <Wrench className="w-5 h-5 text-orange-400" />
          Réparations & dommages
        </h1>
        <p className="text-sm text-dark-400 mt-0.5">
          Retours endommagés, planification maintenances et types de dommages
        </p>
      </div>

      {/* KPI cards */}
      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <KpiSkeleton /><KpiSkeleton /><KpiSkeleton />
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div className="card p-4 text-center">
            <p className="text-xs text-dark-400">À réparer</p>
            <p className="text-2xl font-bold text-orange-400">{kpi.totalRepairs}</p>
          </div>
          <div className="card p-4 text-center">
            <p className="text-xs text-dark-400">Articles</p>
            <p className="text-2xl font-bold">{kpi.totalArticles}</p>
          </div>
          <div className="card p-4 text-center">
            <p className="text-xs text-dark-400">En contrôle</p>
            <p className="text-2xl font-bold text-yellow-400">{kpi.totalPending}</p>
          </div>
        </div>
      )}

      {/* Types de dommages (inline, collapsible) */}
      <div className="card p-4">
        <DamageTypesSection />
      </div>

      {/* Liste retours à réparer */}
      <div>
        <h2 className="text-sm font-medium text-dark-300 mb-2 flex items-center gap-1.5">
          <ArrowDownToLine className="w-4 h-4 text-orange-400" />
          Retours à réparer ({kpi.totalRepairs})
        </h2>

        {isLoading ? (
          <div className="card divide-y divide-dark-600">
            {Array.from({ length: 4 }).map((_, i) => <RowSkeleton key={i} />)}
          </div>
        ) : isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : repairMovements.length === 0 ? (
          <div className="card text-center py-10 text-dark-400">
            <Wrench className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Aucun retour nécessitant réparation</p>
            <p className="text-xs mt-1">Les retours signalés « à réparer » apparaîtront ici</p>
          </div>
        ) : (
          <div className="card divide-y divide-dark-600">
            {repairMovements.map((m) => {
              const chip = getChip(m.status)
              const isExpanded = expandedId === m.id
              return (
                <div key={m.id}>
                  <button
                    onClick={() => toggleExpand(m.id)}
                    className={cn(
                      'flex items-center gap-4 p-4 w-full text-left transition-colors',
                      isExpanded ? 'bg-dark-900/50' : 'hover:bg-dark-600/30',
                    )}
                  >
                    <div className="w-10 h-10 rounded-lg bg-orange-900/20 flex items-center justify-center shrink-0">
                      <Wrench className="w-5 h-5 text-orange-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        Retour {formatDate(m.scheduled_date)} · {m.product_names.join(', ')}
                      </p>
                      <p className="text-xs text-dark-400">
                        {m.items_count} article{m.items_count > 1 ? 's' : ''}
                        {m.reservation_id && (
                          <span className="text-primary-400 ml-1">· Rés. #{m.reservation_id}</span>
                        )}
                      </p>
                    </div>
                    <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium shrink-0', chip.className)}>
                      {chip.label}
                    </span>
                    <ChevronDown
                      className={cn(
                        'w-4 h-4 text-dark-500 transition-transform shrink-0',
                        isExpanded && 'rotate-180 text-primary-400',
                      )}
                    />
                  </button>
                  {isExpanded && <MovementExpansion movementId={m.id} />}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Section contrôles en attente */}
      {!isLoading && pendingMovements.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-dark-300 mb-2 flex items-center gap-1.5">
            <Package className="w-4 h-4 text-yellow-400" />
            En attente de contrôle ({kpi.totalPending})
          </h2>
          <div className="card divide-y divide-dark-600">
            {pendingMovements.map((m) => {
              const chip = getChip(m.status)
              return (
                <div key={m.id} className="flex items-center gap-4 p-4">
                  <div className="w-10 h-10 rounded-lg bg-yellow-900/20 flex items-center justify-center shrink-0">
                    <Package className="w-5 h-5 text-yellow-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      Retour {formatDate(m.scheduled_date)} · {m.product_names.join(', ')}
                    </p>
                    <p className="text-xs text-dark-400">
                      {m.items_count} article{m.items_count > 1 ? 's' : ''}
                      {m.reservation_id && (
                        <span className="text-primary-400 ml-1">· Rés. #{m.reservation_id}</span>
                      )}
                    </p>
                  </div>
                  <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium shrink-0', chip.className)}>
                    {chip.label}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
