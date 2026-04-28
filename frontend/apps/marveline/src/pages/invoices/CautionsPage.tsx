import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { Shield, ChevronLeft, ChevronRight } from 'lucide-react'
import { useDepositsList, useDepositsSummary } from '@/api/queries'
import { formatCents, cn } from '@/lib/utils'
import { FinanceKpiCard, FinanceKpiSkeleton } from '@/pages/finances/components'
import { DomainStatusBadge } from '@shared/components/ui'
import { EmptyState } from '@shared/components/ui/EmptyState'
import type { DepositWithReservation } from '@/api/deposits'

type DepositStatus = 'held' | 'released' | 'retained'

const STATUS_CONFIG: Record<DepositStatus, { label: string; color: string; bg: string }> = {
  held:     { label: 'En attente',  color: 'text-blue-400',   bg: 'bg-blue-500/10 border-blue-500/30' },
  retained: { label: 'Retenue',     color: 'text-red-400',    bg: 'bg-red-500/10 border-red-500/30' },
  released: { label: 'Restituee',   color: 'text-green-400',  bg: 'bg-green-500/10 border-green-500/30' },
}

const FILTER_CHIPS: { key: DepositStatus | 'all'; label: string }[] = [
  { key: 'all',      label: 'Toutes' },
  { key: 'held',     label: 'En attente' },
  { key: 'retained', label: 'Retenues' },
  { key: 'released', label: 'Restituées' },
]

const PAGE_SIZE = 20

function DepositTableSkeleton() {
  return (
    <div className="card overflow-hidden animate-pulse">
      <div className="px-5 py-3.5 border-b border-dark-700">
        <div className="h-4 w-40 bg-dark-700 rounded" />
      </div>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="px-5 py-3.5 flex items-center gap-4 border-b border-dark-700/30">
          <div className="h-3.5 w-20 bg-dark-700 rounded" />
          <div className="h-3.5 w-32 bg-dark-700 rounded flex-1" />
          <div className="h-3.5 w-24 bg-dark-700 rounded" />
          <div className="h-3.5 w-16 bg-dark-700 rounded" />
          <div className="h-5 w-20 bg-dark-700 rounded-full" />
        </div>
      ))}
    </div>
  )
}

function DepositRow({ deposit }: { deposit: DepositWithReservation }) {
  const cfg = STATUS_CONFIG[deposit.status] ?? STATUS_CONFIG.held
  return (
    <tr className="border-b border-dark-700/30 hover:bg-dark-800/30 transition-colors">
      <td className="px-4 py-3">
        <Link
          to="/reservations/$id"
          params={{ id: String(deposit.reservation_id) }}
          className="text-sm font-mono font-semibold text-primary-400 hover:text-primary-300"
        >
          {deposit.reservation_reference}
        </Link>
      </td>
      <td className="px-4 py-3 text-sm text-dark-100 truncate max-w-[200px]">
        {deposit.customer_name || '—'}
      </td>
      <td className="px-4 py-3 text-sm text-dark-300 whitespace-nowrap">
        {deposit.event_date
          ? new Date(deposit.event_date).toLocaleDateString('fr-FR')
          : '—'}
      </td>
      <td className="px-4 py-3 text-sm font-semibold text-dark-50 tabular-nums text-right">
        {formatCents(deposit.amount_cents)}
      </td>
      {deposit.retained_amount_cents ? (
        <td className="px-4 py-3 text-sm text-red-400 tabular-nums text-right">
          {formatCents(deposit.retained_amount_cents)}
        </td>
      ) : (
        <td className="px-4 py-3 text-sm text-dark-500 text-right">—</td>
      )}
      <td className="px-4 py-3">
        <span className={cn('text-xs px-2.5 py-1 rounded-full border font-medium', cfg.bg, cfg.color)}>
          {cfg.label}
        </span>
      </td>
    </tr>
  )
}

export function CautionsPage() {
  const [filter, setFilter] = useState<DepositStatus | 'all'>('all')
  const [page, setPage] = useState(0)

  const params = {
    status: filter === 'all' ? undefined : filter,
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  }

  const { data: summary, isLoading: loadingSummary } = useDepositsSummary()
  const { data: depositsData, isLoading: loadingList, error } = useDepositsList(params)

  const deposits = depositsData?.items ?? []
  const total = depositsData?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Shield className="w-5 h-5 text-primary-400" />
        <PageHeader title="Suivi des cautions" />
        {total > 0 && (
          <span className="text-xs text-dark-400 ml-2">{total} caution{total > 1 ? 's' : ''}</span>
        )}
      </div>

      {/* KPI */}
      {loadingSummary && <FinanceKpiSkeleton count={3} />}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <FinanceKpiCard
            title="En attente"
            value={formatCents(summary.total_held_cents)}
            icon={<Shield className="w-5 h-5" />}
            iconBg="bg-blue-500/10"
            iconColor="text-blue-400"
            valueClass="text-blue-400"
            compact
          />
          <FinanceKpiCard
            title="Retenues"
            value={formatCents(summary.total_retained_cents)}
            icon={<Shield className="w-5 h-5" />}
            iconBg="bg-red-500/10"
            iconColor="text-red-400"
            valueClass="text-red-400"
            compact
          />
          <FinanceKpiCard
            title="Restituées"
            value={formatCents(summary.total_released_cents)}
            icon={<Shield className="w-5 h-5" />}
            iconBg="bg-green-500/10"
            iconColor="text-green-400"
            valueClass="text-green-400"
            compact
          />
        </div>
      )}

      {/* Filtres */}
      <div className="flex gap-2 flex-wrap">
        {FILTER_CHIPS.map((chip) => (
          <button
            key={chip.key}
            onClick={() => { setFilter(chip.key); setPage(0) }}
            className={cn(
              'px-4 py-1.5 rounded-full text-xs font-medium border transition-colors',
              filter === chip.key
                ? 'bg-primary-500 text-white border-primary-500'
                : 'bg-dark-900 border-dark-600 text-dark-400 hover:bg-dark-600'
            )}
          >
            {chip.label}
            {chip.key !== 'all' && summary && (
              <span className="ml-1.5 opacity-70">
                {chip.key === 'held' ? summary.count_held : chip.key === 'retained' ? summary.count_retained : summary.count_released}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Erreur */}
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          Erreur lors du chargement des cautions
        </div>
      )}

      {/* Table */}
      {loadingList && <DepositTableSkeleton />}

      {!loadingList && !error && deposits.length === 0 && (
        <EmptyState
          icon={<Shield className="w-8 h-8" />}
          title={filter === 'all' ? 'Aucune caution enregistrée' : 'Aucune caution dans cet état'}
        />
      )}

      {!loadingList && deposits.length > 0 && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-dark-700">
                  <th className="px-4 py-2.5 text-xs font-medium text-dark-400 text-left">Reservation</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-dark-400 text-left">Client</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-dark-400 text-left">Événement</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-dark-400 text-right">Montant</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-dark-400 text-right">Retenu</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-dark-400 text-left">Statut</th>
                </tr>
              </thead>
              <tbody>
                {deposits.map((dep) => (
                  <DepositRow key={dep.id} deposit={dep} />
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-dark-700">
              <span className="text-xs text-dark-400">
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} sur {total}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="p-1.5 rounded-lg hover:bg-dark-600 disabled:opacity-30 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-xs text-dark-300 tabular-nums">
                  {page + 1} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="p-1.5 rounded-lg hover:bg-dark-600 disabled:opacity-30 transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
