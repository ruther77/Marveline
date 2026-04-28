import { useState } from 'react'
import { useFinancesStats } from '@/api/queries/useDashboard'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer,
} from 'recharts'
import { TrendingUp, AlertTriangle, FileCheck, Calculator } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents, cn } from '@/lib/utils'
import {
  FinanceKpiCard,
  FinanceChartCard,
  FinanceTable,
  FinancePageSkeleton,
} from '@/pages/finances/components'

const MONTHS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
const QUARTER_COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b']

const CURRENT_YEAR = new Date().getFullYear()
const YEAR_OPTIONS = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2]

const QUARTERS: { label: string; months: number[] }[] = [
  { label: 'T1', months: [1, 2, 3] },
  { label: 'T2', months: [4, 5, 6] },
  { label: 'T3', months: [7, 8, 9] },
  { label: 'T4', months: [10, 11, 12] },
]

type ViewMode = 'monthly' | 'quarterly'

function getBarColor(mode: ViewMode, index: number, month: number): string {
  if (mode === 'quarterly') return QUARTER_COLORS[index] ?? '#3b82f6'
  const quarter = Math.floor((month - 1) / 3)
  return QUARTER_COLORS[quarter] ?? '#3b82f6'
}

interface PeriodRow {
  label: string
  index: number
  month: number
  revenue_cents: number
  invoices_paid: number
  invoices_overdue: number
  color: string
  barPct: number
}

export default function FinancesPeriodePage() {
  const [year, setYear] = useState(CURRENT_YEAR)
  const [viewMode, setViewMode] = useState<ViewMode>('monthly')

  const { data, isLoading, error } = useFinancesStats(year)

  if (isLoading) return <FinancePageSkeleton />

  if (error || !data) {
    return (
      <div className="card p-8 text-center text-red-400">
        {error ? normalizeError(error).message : 'Données indisponibles'}
      </div>
    )
  }

  const { monthly, totals } = data

  const quarterlyData = QUARTERS.map((q) => {
    const rows = monthly.filter((m) => q.months.includes(m.month))
    return {
      label: q.label,
      revenue_cents: rows.reduce((s, r) => s + r.revenue_cents, 0),
      invoices_paid: rows.reduce((s, r) => s + r.invoices_paid, 0),
      invoices_overdue: rows.reduce((s, r) => s + r.invoices_overdue, 0),
    }
  })

  const rawRows = viewMode === 'monthly'
    ? monthly.map((m, i) => ({ ...m, label: MONTHS[m.month - 1], index: i }))
    : quarterlyData.map((q, i) => ({ ...q, index: i, month: (i + 1) * 3 }))

  const maxRevenue = Math.max(...rawRows.map((r) => r.revenue_cents), 1)

  const rows: PeriodRow[] = rawRows.map((r, i) => ({
    ...r,
    color: viewMode === 'quarterly' ? QUARTER_COLORS[i] : QUARTER_COLORS[Math.floor(i / 3)],
    barPct: Math.round((r.revenue_cents / maxRevenue) * 100),
  }))

  const chartData = rows.map((r) => ({
    name: r.label,
    value: Math.round(r.revenue_cents / 100),
    index: r.index,
    month: r.month,
  }))

  const avgPerMonth = monthly.length > 0
    ? Math.round(totals.revenue_ytd_cents / monthly.filter((m) => m.revenue_cents > 0).length || 1)
    : 0

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap gap-4 items-center justify-between">
        <div className="flex items-center gap-4">
          <select
            className="input"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {YEAR_OPTIONS.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <div className="flex rounded-xl overflow-hidden border border-dark-600">
            {(['monthly', 'quarterly'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={cn(
                  'px-4 py-2 text-sm font-medium min-h-[44px] transition-colors',
                  viewMode === mode
                    ? 'bg-primary-500 text-white'
                    : 'bg-dark-900 text-dark-300 hover:bg-dark-600',
                )}
              >
                {mode === 'monthly' ? 'Mensuel' : 'Trimestriel'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <FinanceKpiCard
          title={`CA ${year}`}
          value={formatCents(totals.revenue_ytd_cents)}
          icon={<TrendingUp className="w-5 h-5" />}
          iconBg="bg-primary-500/10"
          iconColor="text-primary-400"
        />
        <FinanceKpiCard
          title="Impayés"
          value={formatCents(totals.overdue_amount_cents)}
          icon={<AlertTriangle className="w-5 h-5" />}
          iconBg="bg-red-500/10"
          iconColor="text-red-400"
          valueClass={totals.overdue_amount_cents > 0 ? 'text-red-400' : 'text-dark-300'}
        />
        <FinanceKpiCard
          title="Réservations actives"
          value={totals.active_reservations}
          icon={<FileCheck className="w-5 h-5" />}
          iconBg="bg-green-500/10"
          iconColor="text-green-400"
        />
        <FinanceKpiCard
          title="CA moyen/mois"
          value={formatCents(avgPerMonth)}
          icon={<Calculator className="w-5 h-5" />}
          iconBg="bg-amber-500/10"
          iconColor="text-amber-400"
          valueClass="text-amber-400"
        />
      </div>

      {/* Chart + Table côte à côte */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <FinanceChartCard
          title={`CA ${viewMode === 'monthly' ? 'mensuel' : 'trimestriel'}`}
          subtitle={String(year)}
          className="lg:col-span-3"
        >
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#374151" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6b7280' }} />
              <YAxis
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                tick={{ fontSize: 11, fill: '#6b7280' }}
              />
              <Tooltip
                formatter={((v: number | undefined) => [formatCents((v ?? 0) * 100), 'CA']) as never}
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#d1d5db' }}
              />
              <Bar dataKey="value" name="CA" radius={[6, 6, 0, 0]} maxBarSize={40}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={getBarColor(viewMode, entry.index, entry.month)}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </FinanceChartCard>

        <FinanceTable<PeriodRow>
          title={`Top ${viewMode === 'monthly' ? 'mois' : 'trimestres'}`}
          className="lg:col-span-2"
          keyExtractor={(row) => row.label}
          data={rows}
          maxRows={5}
          columns={[
            {
              key: 'label',
              label: 'Période',
              render: (row) => (
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: row.color }} />
                  <span className="font-medium">{row.label}</span>
                </div>
              ),
            },
            {
              key: 'revenue',
              label: 'CA',
              align: 'right',
              render: (row) => (
                <span className="font-medium tabular-nums">{formatCents(row.revenue_cents)}</span>
              ),
            },
          ]}
        />
      </div>

      {/* Table complète */}
      <FinanceTable<PeriodRow>
        title={`Détail ${viewMode === 'monthly' ? 'mensuel' : 'trimestriel'}`}
        keyExtractor={(row) => row.label}
        data={rows}
        columns={[
          {
            key: 'label',
            label: 'Période',
            render: (row) => (
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: row.color }} />
                <span className="font-medium">{row.label}</span>
              </div>
            ),
          },
          {
            key: 'revenue',
            label: 'CA',
            align: 'right',
            render: (row) => (
              <div className="flex items-center justify-end gap-2">
                <div className="h-1.5 bg-dark-800 rounded-full w-16 overflow-hidden hidden sm:block">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${row.barPct}%`, backgroundColor: row.color }}
                  />
                </div>
                <span className="font-medium tabular-nums">{formatCents(row.revenue_cents)}</span>
              </div>
            ),
          },
          {
            key: 'invoices_paid',
            label: 'Payées',
            align: 'right',
            render: (row) => (
              <span className="tabular-nums text-green-400">{row.invoices_paid || '--'}</span>
            ),
          },
          {
            key: 'invoices_overdue',
            label: 'En retard',
            align: 'right',
            render: (row) =>
              row.invoices_overdue > 0 ? (
                <span className="font-medium text-red-400 tabular-nums">{row.invoices_overdue}</span>
              ) : (
                <span className="text-dark-600">--</span>
              ),
          },
        ]}
      />
    </div>
  )
}
