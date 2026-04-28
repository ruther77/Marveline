import { useState, useMemo } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { useNavigate } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/api/queries/keys'
import { Package, AlertTriangle, Wrench, Download, ChevronRight, ClipboardCheck } from 'lucide-react'
import { Modal } from '@shared/components/ui/Modal'
import { Button } from '@shared/components/ui/Button'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { usePendingInspections, useDeclareCasse, useDamageTypesList } from '@/api/queries'
import { cn, formatDate, formatCents } from '@/lib/utils'
import type { InventoryMovementListItem, MovementStatus } from '@/types/inventory'
import type { DamageType } from '@/types/damage_type'

// ── Chips status ─────────────────────────────────────────────────────────────

const STATUS_CHIP: Record<string, { label: string; className: string }> = {
  scheduled:  { label: 'Contrôle',  className: 'bg-yellow-900/40 text-yellow-300 border border-yellow-700/40' },
  in_transit: { label: 'À réparer', className: 'bg-orange-900/40 text-orange-300 border border-orange-700/40' },
  completed:  { label: 'Clôturé',   className: 'bg-green-900/40 text-green-300 border border-green-700/40' },
}

function getChip(status: MovementStatus) {
  return STATUS_CHIP[status] ?? { label: status, className: 'bg-dark-900 text-dark-300' }
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function RowSkeleton() {
  return (
    <div className="flex items-center gap-4 p-4 animate-pulse">
      <div className="w-10 h-10 rounded-lg skel shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3 skel rounded w-2/3" />
        <div className="h-2 skel rounded w-1/2" />
      </div>
      <div className="h-5 w-16 skel rounded-full" />
    </div>
  )
}

// ── CSV export helper ────────────────────────────────────────────────────────

function exportInspectionsCsv(movements: InventoryMovementListItem[]) {
  const header = ['ID', 'Date prévue', 'Statut', 'Articles', 'Nb articles', 'Réservation']
  const rows = movements.map((m) => [
    m.id,
    m.scheduled_date,
    m.status,
    m.product_names.join(' | '),
    m.items_count,
    m.reservation_id ?? '',
  ])

  const csv = [header, ...rows].map((r) => r.map((c) => `"${c}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `rapport-retours-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Damage form (inline) ─────────────────────────────────────────────────────

interface DamageFormProps {
  movement: InventoryMovementListItem
  damageTypes: DamageType[]
  onCancel: () => void
  onSuccess: () => void
}

function DamageForm({ movement, damageTypes, onCancel, onSuccess }: DamageFormProps) {
  const qc = useQueryClient()
  const declareMutation = useDeclareCasse()

  const [damageTypeName, setDamageTypeName] = useState(damageTypes[0]?.name ?? '')
  const [description, setDescription] = useState('')
  const [feeCents, setFeeCents] = useState<number | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)

  // Auto-fill fee from selected damage type
  const selectedType = damageTypes.find((t) => t.name === damageTypeName)

  const handleSubmit = () => {
    if (!movement.reservation_id) return
    setError(null)
    declareMutation.mutate(
      {
        reservationId: movement.reservation_id,
        payload: {
          description,
          damage_type_name: damageTypeName,
          fee_cents: feeCents ?? selectedType?.default_fee_cents,
        },
      },
      {
        onSuccess: () => {
          qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.lists() })
          onSuccess()
        },
        onError: (err) =>
          setError(
            normalizeError(err).message || 'Erreur lors de la déclaration'
          ),
      },
    )
  }

  return (
    <div className="card p-4 space-y-4 border border-primary-500/20">
      <p className="text-sm font-medium">
        Dommage — Retour #{movement.id}
        {movement.reservation_id && <span className="text-primary-400 ml-1">· Rés. #{movement.reservation_id}</span>}
      </p>

      <div className="space-y-2">
        <label className="block text-xs text-dark-400">Type de dommage</label>
        <select
          value={damageTypeName}
          onChange={(e) => setDamageTypeName(e.target.value)}
          className="input w-full text-sm"
        >
          {damageTypes.map((t) => (
            <option key={t.id} value={t.name}>
              {t.name} ({formatCents(t.default_fee_cents)})
            </option>
          ))}
          <option value="autre">Autre</option>
        </select>
      </div>

      <div className="space-y-2">
        <label className="block text-xs text-dark-400">Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Décrivez le dommage constaté…"
          className="input w-full text-sm min-h-[60px]"
          rows={2}
        />
      </div>

      <div className="space-y-2">
        <label className="block text-xs text-dark-400">
          Frais (centimes) — par défaut : {selectedType ? formatCents(selectedType.default_fee_cents) : '—'}
        </label>
        <input
          type="number"
          value={feeCents ?? ''}
          onChange={(e) => setFeeCents(e.target.value ? Number(e.target.value) : undefined)}
          placeholder={selectedType ? String(selectedType.default_fee_cents) : '0'}
          className="input w-full text-sm"
          min={0}
        />
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      <div className="flex gap-2 justify-end">
        <Button variant="ghost" size="sm" onClick={onCancel}>Annuler</Button>
        <Button
          variant="primary"
          size="sm"
          loading={declareMutation.isPending}
          disabled={!description.trim() || !damageTypeName}
          onClick={handleSubmit}
        >
          Confirmer le dommage
        </Button>
      </div>
    </div>
  )
}

// ── Props ────────────────────────────────────────────────────────────────────

interface ReturnCheckModalProps {
  isOpen: boolean
  onClose: () => void
}

// ── Modal ────────────────────────────────────────────────────────────────────

export default function ReturnCheckModal({ isOpen, onClose }: ReturnCheckModalProps) {
  const navigate = useNavigate()
  const { data: inspections, isLoading, isError, refetch } = usePendingInspections()

  // Damage types pour le formulaire
  const { data: damageTypesData } = useDamageTypesList()
  const damageTypes = damageTypesData?.items ?? []

  const movements = useMemo(() => inspections ?? [], [inspections])

  // Sélection d'un mouvement pour action
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [showDamageForm, setShowDamageForm] = useState(false)

  const selectedMovement = movements.find((m) => m.id === selectedId)

  // KPI info-grid
  const kpi = useMemo(() => {
    const total = movements.length
    const damaged = movements.filter((m) => m.status === 'in_transit').length
    const pctDamaged = total > 0 ? Math.round((damaged / total) * 100) : 0
    return { total, damaged, pctDamaged }
  }, [movements])

  const handleDeclareDamage = () => {
    if (!selectedMovement?.reservation_id) return
    setShowDamageForm(true)
  }

  const handlePlanRepairs = () => {
    onClose()
    navigate({ to: '/stock/repairs' as never })
  }

  const handleExportReport = () => {
    exportInspectionsCsv(movements)
  }

  const handleDamageSuccess = () => {
    setShowDamageForm(false)
    setSelectedId(null)
  }

  // Reset state on close
  const handleClose = () => {
    setSelectedId(null)
    setShowDamageForm(false)
    onClose()
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Vérifier l'état retour" size="lg">
      <div className="space-y-4">
        {/* Info-grid KPI */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div className="card p-4 text-center">
            <p className="text-xs text-dark-400">Retours à vérifier</p>
            <p className="text-xl font-bold text-orange-400">{kpi.total}</p>
          </div>
          <div className="card p-4 text-center">
            <p className="text-xs text-dark-400">% endommagé</p>
            <p className="text-xl font-bold text-red-400">{kpi.pctDamaged}%</p>
          </div>
          <div className="card p-4 text-center">
            <p className="text-xs text-dark-400">Articles</p>
            <p className="text-xl font-bold">{movements.reduce((s, m) => s + m.items_count, 0)}</p>
          </div>
        </div>

        {/* Instructions */}
        <p className="text-xs text-dark-400 bg-dark-900 rounded-lg p-4">
          Sélectionnez un retour pour contrôler les articles (quantités, état). Vous pouvez aussi déclarer un dommage rapide ou planifier des réparations.
        </p>

        {/* Liste */}
        {isLoading ? (
          <div className="card divide-y divide-dark-600">
            {Array.from({ length: 3 }).map((_, i) => (
              <RowSkeleton key={i} />
            ))}
          </div>
        ) : isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : movements.length === 0 ? (
          <div className="text-center py-8 text-dark-400">
            <Package className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Aucun retour en attente de vérification</p>
          </div>
        ) : (
          <div className="card divide-y divide-dark-600 max-h-64 overflow-y-auto">
            {movements.map((m) => {
              const chip = getChip(m.status)
              const code = m.product_names[0]?.slice(0, 3).toUpperCase() ?? '???'
              const isSelected = selectedId === m.id
              return (
                <button
                  key={m.id}
                  onClick={() => { setSelectedId(isSelected ? null : m.id); setShowDamageForm(false) }}
                  className={cn(
                    'flex items-center gap-4 p-4 w-full text-left transition-colors',
                    isSelected
                      ? 'bg-primary-500/10 ring-1 ring-primary-500/30'
                      : 'hover:bg-dark-600/50',
                  )}
                >
                  <div className="w-10 h-10 rounded-lg bg-dark-950 flex items-center justify-center shrink-0 text-xs font-bold text-dark-300">
                    {code}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      Retour {formatDate(m.scheduled_date)} · {m.product_names.join(', ')}
                    </p>
                    <p className="text-xs text-dark-400">
                      {m.items_count} article{m.items_count > 1 ? 's' : ''}
                      {m.reservation_id && <span className="text-primary-400 ml-1">· Rés. #{m.reservation_id}</span>}
                    </p>
                  </div>
                  <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium shrink-0', chip.className)}>
                    {chip.label}
                  </span>
                  <ChevronRight className={cn('w-4 h-4 text-dark-500 transition-transform', isSelected && 'rotate-90 text-primary-400')} />
                </button>
              )
            })}
          </div>
        )}

        {/* Bouton contrôle retour détaillé */}
        {selectedMovement?.reservation_id && !showDamageForm && (
          <Button
            variant="primary"
            className="w-full"
            onClick={() => {
              onClose()
              navigate({
                to: '/operations/return/$reservationId' as never,
                params: { reservationId: String(selectedMovement.reservation_id) } as never,
              })
            }}
          >
            <ClipboardCheck className="w-4 h-4 mr-1.5" />
            Contrôler le retour — Rés. #{selectedMovement.reservation_id}
          </Button>
        )}

        {/* Formulaire dommage inline */}
        {showDamageForm && selectedMovement && (
          <DamageForm
            movement={selectedMovement}
            damageTypes={damageTypes}
            onCancel={() => setShowDamageForm(false)}
            onSuccess={handleDamageSuccess}
          />
        )}

        {/* Actions */}
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1"
              disabled={!selectedMovement?.reservation_id || showDamageForm}
              onClick={handleDeclareDamage}
            >
              <AlertTriangle className="w-4 h-4 mr-1.5" />
              Déclarer un dommage
            </Button>
            <Button
              variant="secondary"
              className="flex-1"
              disabled={kpi.damaged === 0}
              onClick={handlePlanRepairs}
            >
              <Wrench className="w-4 h-4 mr-1.5" />
              Planifier réparations
            </Button>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1"
              disabled={movements.length === 0}
              onClick={handleExportReport}
            >
              <Download className="w-4 h-4 mr-1.5" />
              Exporter rapport
            </Button>
            <Button variant="ghost" className="flex-1" onClick={handleClose}>
              Fermer
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  )
}
