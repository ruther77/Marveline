import { PageHeader } from '@/components/PageHeader'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useFinancesStats } from '@/api/queries/useDashboard'
import {
  ComposedChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { Euro, AlertTriangle, Award, FileCheck } from 'lucide-react'
import { formatCents, cn } from '@/lib/utils'
import type { FinancesMonthly } from '@/types/dashboard'
import {
  FinanceKpiCard,
  FinanceChartCard,
  FinanceTable,
  FinancePageSkeleton,
} from '@/pages/finances/components'
import { NoData, ErrorState } from '@shared/components/ui/EmptyState'

const MONTHS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
const CURRENT_YEAR = new Date().getFullYear()
const YEAR_OPTIONS = [CURRENT_YEAR - 2, CURRENT_YEAR - 1, CURRENT_YEAR, CURRENT_YEAR + 1]

// ── Data helpers ─────────────────────────────────────────────────────────────

function buildComparisonData(cur: FinancesMonthly[], prev: FinancesMonthly[]) {
  return cur.map((m, i) => ({
    name: MONTHS[m.month - 1],
    current: Math.round(m.revenue_cents / 100),
    previous: Math.round((prev[i]?.revenue_cents ?? 0) / 100),
  }))
}

function buildCumulativeData(monthly: FinancesMonthly[]) {
  let acc = 0
  return monthly.map((m) => {
    acc += m.revenue_cents
    return { name: MONTHS[m.month - 1], total: Math.round(acc / 100) }
  })
}

// ── Tooltips ─────────────────────────────────────────────────────────────────

function RevenueTooltip({ active, payload, label, prevYear }: {
  active?: boolean; payload?: { value: number; dataKey: string }[]; label?: string; prevYear: number
}) {
  if (!active || !payload?.length) return null
  const cur = payload.find((p) => p.dataKey === 'current')?.value ?? 0
  const prev = payload.find((p) => p.dataKey === 'previous')?.value ?? 0
  const delta = prev > 0 ? ((cur - prev) / prev) * 100 : null
  return (
    <div className="card p-3 text-xs shadow-xl">
      <p className="font-semibold mb-1 text-dark-200">{label}</p>
      <p className="text-blue-400">{formatCents(cur * 100)}</p>
      <p className="text-dark-400">{prevYear} : {formatCents(prev * 100)}</p>
      {delta != null && (
        <p className={cn('mt-1 font-medium', delta >= 0 ? 'text-green-400' : 'text-red-400')}>
          {delta >= 0 ? '+' : ''}{delta.toFixed(1)}%
        </p>
      )}
    </div>
  )
}

// ── Monthly table columns ────────────────────────────────────────────────────

interface MonthRow {
  month: number
  revenue_cents: number
  invoices_paid: number
  invoices_overdue: number
  delta: number | null
  barPct: number
}

function buildMonthRows(
  monthly: FinancesMonthly[],
  prevMonthly: FinancesMonthly[],
): MonthRow[] {
  const maxRevenue = Math.max(...monthly.map((m) => m.revenue_cents), 1)
  return monthly.map((m, i) => {
    const prevRev = prevMonthly[i]?.revenue_cents ?? 0
    return {
      ...m,
      delta: prevRev > 0 ? ((m.revenue_cents - prevRev) / prevRev) * 100 : null,
      barPct: Math.round((m.revenue_cents / maxRevenue) * 100),
    }
  })
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function FinancesPage() {
  const navigate = useNavigate()
  const { year: urlYear = CURRENT_YEAR } = useSearch({ strict: false }) as { year?: number }
  const year = urlYear

  const { data, isLoading, error, refetch } = useFinancesStats(year)
  const { data: dataPrev } = useFinancesStats(year - 1)

  if (isLoading) return <FinancePageSkeleton />

  if (error) return <ErrorState onRetry={() => refetch()} />

  if (!data) return <NoData />

  const prevMonthly = dataPrev?.monthly ?? Array.from({ length: 12 }, (_, i) => ({
    month: i + 1, revenue_cents: 0, invoices_paid: 0, invoices_overdue: 0,
  }))

  const comparisonData = buildComparisonData(data.monthly, prevMonthly)
  const cumulativeData = buildCumulativeData(data.monthly)

  const revYtd = data.totals.revenue_ytd_cents
  const revPrevYtd = dataPrev?.totals.revenue_ytd_cents ?? 0
  const variation = revPrevYtd > 0 ? ((revYtd - revPrevYtd) / revPrevYtd) * 100 : null

  const bestMonth = data.monthly.reduce(
    (best, m) => (m.revenue_cents > best.revenue_cents ? m : best),
    data.monthly[0],
  )
  const totalPaid = data.monthly.reduce((s, m) => s + m.invoices_paid, 0)
  const monthRows = buildMonthRows(data.monthly, prevMonthly)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <PageHeader title="Synthèse financière" subtitle="Vue annuelle — comparaison N vs N-1" />
        <select
          value={year}
          onChange={(e) => navigate({ search: (prev: Record<string, unknown>) => ({ ...prev, year: Number(e.target.value) }) })}
          className="input"
        >
          {YEAR_OPTIONS.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <FinanceKpiCard
          title={`CA encaissé ${year}`}
          value={formatCents(revYtd)}
          icon={<Euro className="w-5 h-5" />}
          iconBg="bg-primary-500/10"
          iconColor="text-primary-400"
          variation={variation}
        />
        <FinanceKpiCard
          title="Factures payées"
          value={totalPaid}
          icon={<FileCheck className="w-5 h-5" />}
          iconBg="bg-green-500/10"
          iconColor="text-green-400"
          valueClass="text-green-400"
        />
        <FinanceKpiCard
          title="Impayés en cours"
          value={formatCents(data.totals.overdue_amount_cents)}
          icon={<AlertTriangle className="w-5 h-5" />}
          iconBg="bg-red-500/10"
          iconColor="text-red-400"
          valueClass={data.totals.overdue_amount_cents > 0 ? 'text-red-400' : 'text-dark-300'}
        />
        <FinanceKpiCard
          title="Meilleur mois"
          value={bestMonth ? MONTHS[bestMonth.month - 1] : '--'}
          icon={<Award className="w-5 h-5" />}
          iconBg="bg-amber-500/10"
          iconColor="text-amber-400"
          valueClass="text-gold-400"
        />
      </div>

      {/* Charts — côte à côte */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Chart 1 : Comparaison N vs N-1 */}
        <FinanceChartCard
          title="CA mensuel"
          subtitle={`${year} vs ${year - 1}`}
        >
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={comparisonData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#374151" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6b7280' }} />
              <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11, fill: '#6b7280' }} />
              <Tooltip content={(props) => (
                <RevenueTooltip
                  active={props.active}
                  payload={props.payload as unknown as { value: number; dataKey: string }[] | undefined}
                  label={props.label as string | undefined}
                  prevYear={year - 1}
                />
              )} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="current" name={String(year)} fill="#3b82f6" radius={[4, 4, 0, 0]} maxBarSize={28} />
              <Bar dataKey="previous" name={String(year - 1)} fill="#374151" radius={[4, 4, 0, 0]} maxBarSize={28} />
            </ComposedChart>
          </ResponsiveContainer>
        </FinanceChartCard>

        {/* Chart 2 : CA cumulatif */}
        <FinanceChartCard
          title="CA cumulatif"
          subtitle={String(year)}
        >
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={cumulativeData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#374151" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6b7280' }} />
              <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11, fill: '#6b7280' }} />
              <Tooltip formatter={((v: number | undefined) => [formatCents((v ?? 0) * 100), 'CA cumulé']) as never} />
              <Area
                type="monotone"
                dataKey="total"
                stroke="#3b82f6"
                strokeWidth={2}
                fill="url(#areaGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </FinanceChartCard>
      </div>

      {/* Table mensuel */}
      <FinanceTable<MonthRow>
        title="Détail mensuel"
        keyExtractor={(row) => row.month}
        data={monthRows}
        columns={[
          {
            key: 'month',
            label: 'Mois',
            render: (row) => (
              <span className="font-medium text-dark-200">{MONTHS[row.month - 1]}</span>
            ),
          },
          {
            key: 'revenue',
            label: 'CA',
            align: 'right',
            render: (row) => (
              <div className="flex items-center justify-end gap-2">
                <div className="w-16 h-1.5 bg-dark-800 rounded-full overflow-hidden hidden sm:block">
                  <div
                    className="h-full bg-primary-500 rounded-full transition-all"
                    style={{ width: `${row.barPct}%` }}
                  />
                </div>
                <span className="tabular-nums font-medium">{formatCents(row.revenue_cents)}</span>
              </div>
            ),
          },
          {
            key: 'delta',
            label: 'vs N-1',
            align: 'right',
            render: (row) =>
              row.delta != null ? (
                <span className={cn('text-xs font-medium', row.delta >= 0 ? 'text-green-400' : 'text-red-400')}>
                  {row.delta >= 0 ? '+' : ''}{row.delta.toFixed(1)}%
                </span>
              ) : (
                <span className="text-dark-600">--</span>
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
