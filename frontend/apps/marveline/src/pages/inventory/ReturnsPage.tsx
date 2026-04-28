import { PageHeader } from '@/components/PageHeader'
import { useMemo } from 'react'
import { Link } from '@tanstack/react-router'
import {
  RotateCcw,
  AlertTriangle,
  CheckCircle,
  ClipboardCheck,
  Download,
  Wrench,
  Package,
  ChevronRight,
  Camera,
} from 'lucide-react'
import { usePendingInspections } from '@/api/queries'
import { Button, Progress } from '@shared/components/ui'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { cn, formatDate } from '@/lib/utils'
import type { InventoryMovementListItem, MovementStatus } from '@/types/inventory'

// ── Status chips ─────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  scheduled:  { label: 'À contrôler', className: 'bg-yellow-900/40 text-yellow-300 border border-yellow-700/40' },
  in_transit: { label: 'À réparer',   className: 'bg-orange-900/40 text-orange-300 border border-orange-700/40' },
  completed:  { label: 'Clôturé',     className: 'bg-green-900/40 text-green-300 border border-green-700/40' },
}

function getChip(status: MovementStatus) {
  return STATUS_CONFIG[status] ?? { label: status, className: 'bg-dark-900 text-dark-300' }
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function RowSkeleton() {
  return (
    <div className="flex items-center gap-4 p-4 animate-pulse">
      <div className="w-10 h-10 rounded-lg skel shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 skel rounded w-2/3" />
        <div className="h-2.5 skel rounded w-1/2" />
      </div>
      <div className="h-5 w-16 skel rounded-full" />
    </div>
  )
}

// ── CSV export ───────────────────────────────────────────────────────────────

function exportCsv(movements: InventoryMovementListItem[]) {
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

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ReturnsPage() {
  const { data: inspections, isLoading, isError, refetch } = usePendingInspections()
  const movements = useMemo(() => inspections ?? [], [inspections])

  // KPI
  const kpi = useMemo(() => {
    const total = movements.length
    const toCheck = movements.filter((m) => m.status === 'scheduled').length
    const damaged = movements.filter((m) => m.status === 'in_transit').length
    const done = movements.filter((m) => m.status === 'completed').length
    const pctDone = total > 0 ? Math.round((done / total) * 100) : 0
    return { total, toCheck, damaged, done, pctDone }
  }, [movements])

  // ── Loading ─────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <RotateCcw className="w-5 h-5 text-amber-400" />
          <PageHeader title="Contrôle retours" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="card p-4 animate-pulse">
              <div className="h-2.5 skel rounded w-16 mx-auto mb-2" />
              <div className="h-6 skel rounded w-10 mx-auto" />
            </div>
          ))}
        </div>
        <div className="card divide-y divide-dark-600">
          {Array.from({ length: 4 }).map((_, i) => (
            <RowSkeleton key={i} />
          ))}
        </div>
      </div>
    )
  }

  // ── Error ───────────────────────────────────────────────────────────────
  if (isError) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <RotateCcw className="w-5 h-5 text-amber-400" />
          <h1 className="text-xl font-semibold">Contrôle retours</h1>
        </div>
        <ErrorState onRetry={() => refetch()} />
      </div>
    )
  }

  // ── Empty ───────────────────────────────────────────────────────────────
  if (movements.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <RotateCcw className="w-5 h-5 text-amber-400" />
          <h1 className="text-xl font-semibold">Contrôle retours</h1>
        </div>
        <div className="text-center py-12 text-dark-400">
          <Package className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-sm font-medium">Aucun retour en attente</p>
          <p className="text-xs mt-1">Tous les retours ont été contrôlés.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <RotateCcw className="w-5 h-5 text-amber-400" />
          <div>
            <h1 className="text-xl font-semibold">Contrôle retours</h1>
            <p className="text-sm text-dark-400 mt-0.5">
              Vérifier quantités et état des articles retournés
            </p>
          </div>
        </div>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div className="card p-4 text-center">
          <p className="text-xs text-dark-400">À contrôler</p>
          <p className="text-xl font-bold text-yellow-400">{kpi.toCheck}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-xs text-dark-400">Endommagés</p>
          <p className={cn('text-xl font-bold', kpi.damaged > 0 ? 'text-red-400' : 'text-dark-500')}>{kpi.damaged}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-xs text-dark-400">Clôturés</p>
          <p className="text-xl font-bold text-green-400">{kpi.done}</p>
        </div>
      </div>

      {/* Progress */}
      <Progress
        value={kpi.done}
        max={kpi.total}
        variant={kpi.damaged > 0 ? 'warning' : 'success'}
        size="sm"
        label={`${kpi.done}/${kpi.total} inspectés`}
        showLabel
      />

      {/* Instructions */}
      <p className="text-xs text-dark-400 bg-dark-900 rounded-lg p-4">
        Sélectionnez un retour pour contrôler les articles : quantités reçues, état constaté, déclaration de dommages si nécessaire.
      </p>

      {/* Liste des retours */}
      <div className="card divide-y divide-dark-600">
        {movements.map((m) => {
          const chip = getChip(m.status)
          const code = m.product_names[0]?.slice(0, 3).toUpperCase() ?? '???'
          const href = m.reservation_id != null
            ? `/operations/return/${m.reservation_id}`
            : `/stock/movements`

          return (
            <Link
              key={m.id}
              to={href}
              className="flex items-center gap-4 p-4 w-full text-left transition-colors hover:bg-dark-600/50 active:scale-[0.99]"
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
                  {m.reservation_id != null && (
                    <span className="text-primary-400 ml-1">· Rés. #{m.reservation_id}</span>
                  )}
                </p>
              </div>
              <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium shrink-0', chip.className)}>
                {chip.label}
              </span>
              <ChevronRight className="w-4 h-4 text-dark-500" />
            </Link>
          )
        })}
      </div>

      {/* Actions */}
      <div className="flex gap-4">
        <Button
          variant="secondary"
          className="flex-1"
          disabled={kpi.damaged === 0}
          leftIcon={<Wrench className="w-4 h-4" />}
          onClick={() => window.location.assign('/stock/repairs')}
        >
          Réparations
        </Button>
        <Button
          variant="outline"
          className="flex-1"
          disabled={movements.length === 0}
          leftIcon={<Download className="w-4 h-4" />}
          onClick={() => exportCsv(movements)}
        >
          Exporter
        </Button>
      </div>
    </div>
  )
}
