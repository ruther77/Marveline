import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { normalizeError } from '@shared/errors/normalizer'
import { useTreasuryEntries, useTreasurySummary } from '@/api/queries/useTreasury'
import { formatCents, cn } from '@/lib/utils'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import {
  Wallet, Hash, Shield, CreditCard, Banknote, ArrowDownCircle,
  ChevronLeft, ChevronRight, Download,
} from 'lucide-react'
import {
  FinanceKpiCard,
  FinanceKpiSkeleton,
} from '@/pages/finances/components'
import { EmptyState } from '@shared/components/ui/EmptyState'
import type { TreasuryEntry } from '@/api/treasury'

type ViewMode = 'all' | 'payments' | 'deposits'

const VIEW_TABS: { key: ViewMode; label: string; icon: React.ReactNode }[] = [
  { key: 'all',      label: 'Vue globale', icon: <Wallet className="w-4 h-4" /> },
  { key: 'payments',  label: 'Paiements',  icon: <CreditCard className="w-4 h-4" /> },
  { key: 'deposits',  label: 'Cautions',   icon: <Shield className="w-4 h-4" /> },
]

const METHOD_LABELS: Record<string, string> = {
  cash: 'Especes', card: 'Carte', transfer: 'Virement', check: 'Cheque',
}

const METHOD_COLORS: Record<string, string> = {
  cash: '#10b981', card: '#3b82f6', transfer: '#8b5cf6', check: '#f59e0b',
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  held:     { label: 'En attente', color: 'text-blue-400',  bg: 'bg-blue-500/10 border-blue-500/30' },
  retained: { label: 'Retenue',    color: 'text-red-400',   bg: 'bg-red-500/10 border-red-500/30' },
  released: { label: 'Restituee',  color: 'text-green-400', bg: 'bg-green-500/10 border-green-500/30' },
}

const PAGE_SIZE = 30

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function EntryTypeBadge({ type }: { type: 'deposit' | 'payment' }) {
  if (type === 'deposit') {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/30">
        Caution
      </span>
    )
  }
  return (
    <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/10 text-green-400 border border-green-500/30">
      Paiement
    </span>
  )
}

export function TresorerieePage() {
  const today = new Date().toISOString().slice(0, 10)
  const firstOfMonth = today.slice(0, 8) + '01'

  const [view, setView] = useState<ViewMode>('all')
  const [dateFrom, setDateFrom] = useState(firstOfMonth)
  const [dateTo, setDateTo] = useState(today)
  const [page, setPage] = useState(0)

  const entryType = view === 'all' ? undefined : view === 'payments' ? 'payment' : 'deposit'

  const { data: summary, isLoading: loadingSummary } = useTreasurySummary({
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  })

  const { data: entriesData, isLoading: loadingEntries, error } = useTreasuryEntries({
    entry_type: entryType,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  })

  const entries = entriesData?.items ?? []
  const total = entriesData?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const donutData = summary
    ? Object.entries(summary.by_method)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => ({
          name: METHOD_LABELS[k] ?? k,
          value: Math.round(v / 100),
          color: METHOD_COLORS[k] ?? '#6b7280',
        }))
    : []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <PageHeader
          title="Tresorerie"
          subtitle="Vue unifiee des paiements et cautions"
        />
        <a
          href={`/api/v1/treasury/export-csv?${new URLSearchParams({
            ...(dateFrom ? { date_from: dateFrom } : {}),
            ...(dateTo ? { date_to: dateTo } : {}),
          }).toString()}`}
          download
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium border border-dark-600 hover:border-dark-400 text-dark-200 rounded-lg transition-colors shrink-0"
        >
          <Download className="w-4 h-4" />
          Export CSV
        </a>
      </div>

      {/* Onglets */}
      <div className="flex gap-2 flex-wrap">
        {VIEW_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => { setView(tab.key); setPage(0) }}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium border transition-colors',
              view === tab.key
                ? 'bg-primary-500 text-white border-primary-500'
                : 'bg-dark-900 border-dark-600 text-dark-400 hover:bg-dark-600'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Filtres dates */}
      <div className="card p-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs text-dark-400 mb-1">Du</label>
            <input
              type="date" value={dateFrom}
              onChange={(e) => { setDateFrom(e.target.value); setPage(0) }}
              className="input w-full"
            />
          </div>
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs text-dark-400 mb-1">Au</label>
            <input
              type="date" value={dateTo}
              onChange={(e) => { setDateTo(e.target.value); setPage(0) }}
              className="input w-full"
            />
          </div>
        </div>
      </div>

      {/* Erreur */}
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {normalizeError(error).message || 'Erreur lors du chargement'}
        </div>
      )}

      {/* KPI */}
      {loadingSummary ? (
        <FinanceKpiSkeleton count={4} />
      ) : summary ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <FinanceKpiCard
            title="Total encaisse"
            value={formatCents(summary.total_collected_cents)}
            icon={<Wallet className="w-5 h-5" />}
            iconBg="bg-primary-500/10"
            iconColor="text-primary-400"
          />
          <FinanceKpiCard
            title="Paiements"
            value={formatCents(summary.payments_total_cents)}
            icon={<CreditCard className="w-5 h-5" />}
            iconBg="bg-green-500/10"
            iconColor="text-green-400"
            compact
          />
          <FinanceKpiCard
            title="Cautions tenues"
            value={formatCents(summary.deposits_held_cents)}
            icon={<Shield className="w-5 h-5" />}
            iconBg="bg-blue-500/10"
            iconColor="text-blue-400"
            compact
          />
          <FinanceKpiCard
            title="Cautions retenues"
            value={formatCents(summary.deposits_retained_cents)}
            icon={<ArrowDownCircle className="w-5 h-5" />}
            iconBg="bg-red-500/10"
            iconColor="text-red-400"
            compact
          />
        </div>
      ) : null}

      {/* Chart donut (paiements uniquement) */}
      {donutData.length > 0 && (view === 'all' || view === 'payments') && (
        <div className="card p-4">
          <h3 className="text-sm font-medium text-dark-200 mb-3">Repartition par methode</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie
                data={donutData}
                cx="50%" cy="50%"
                innerRadius={45} outerRadius={70}
                dataKey="value" paddingAngle={3}
              >
                {donutData.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={((v: number) => [formatCents(v * 100)]) as never}
                contentStyle={{
                  backgroundColor: '#1f2937',
                  border: '1px solid #374151',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-4 mt-2">
            {donutData.map((d) => (
              <div key={d.name} className="flex items-center gap-1.5 text-xs text-dark-300">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.color }} />
                {d.name}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Table unifiee */}
      {loadingEntries && (
        <div className="card overflow-hidden animate-pulse">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="px-5 py-3.5 flex items-center gap-4 border-b border-dark-700/30">
              <div className="h-3.5 w-16 bg-dark-700 rounded" />
              <div className="h-3.5 w-24 bg-dark-700 rounded" />
              <div className="h-3.5 w-32 bg-dark-700 rounded flex-1" />
              <div className="h-3.5 w-20 bg-dark-700 rounded" />
            </div>
          ))}
        </div>
      )}

      {!loadingEntries && !error && entries.length === 0 && (
        <EmptyState
          icon={<Wallet className="w-8 h-8" />}
          title="Aucun mouvement sur cette periode"
        />
      )}

      {!loadingEntries && entries.length > 0 && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-dark-700">
                  <th className="px-4 py-2.5 text-xs font-medium text-dark-400 text-left">Date</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-dark-400 text-left">Type</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-dark-400 text-left">Reference</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-dark-400 text-left">Detail</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-dark-400 text-right">Montant</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, i) => (
                  <EntryRow key={`${entry.entry_type}-${entry.source_id}-${i}`} entry={entry} />
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

function EntryRow({ entry }: { entry: TreasuryEntry }) {
  const isDeposit = entry.entry_type === 'deposit'
  const statusCfg = isDeposit && entry.status ? STATUS_CONFIG[entry.status] : null

  return (
    <tr className="border-b border-dark-700/30 hover:bg-dark-800/30 transition-colors">
      <td className="px-4 py-3 text-sm text-dark-300 whitespace-nowrap">
        {formatDate(entry.entry_date)}
      </td>
      <td className="px-4 py-3">
        <EntryTypeBadge type={entry.entry_type} />
      </td>
      <td className="px-4 py-3 text-sm font-mono text-primary-400">
        {isDeposit && entry.source_id ? (
          <Link
            to="/reservations/$id"
            params={{ id: String(entry.source_id) }}
            className="hover:text-primary-300"
          >
            {entry.reference ?? `#${entry.source_id}`}
          </Link>
        ) : (
          <span>{entry.reference ?? `#${entry.source_id}`}</span>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-dark-300">
        {isDeposit && statusCfg ? (
          <span className={cn('text-xs px-2 py-0.5 rounded-full border', statusCfg.bg, statusCfg.color)}>
            {statusCfg.label}
          </span>
        ) : entry.method ? (
          <span className="capitalize">{METHOD_LABELS[entry.method] ?? entry.method}</span>
        ) : (
          '—'
        )}
        {entry.customer_name && (
          <span className="ml-2 text-dark-400">{entry.customer_name}</span>
        )}
      </td>
      <td className="px-4 py-3 text-sm font-semibold tabular-nums text-right">
        {formatCents(entry.amount_cents)}
      </td>
    </tr>
  )
}
