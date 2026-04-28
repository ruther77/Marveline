import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { formatCents, cn } from '@/lib/utils'
import {
  BarChart3, ChevronLeft, ChevronRight, TrendingUp, Download,
  FileCheck, AlertTriangle, CalendarCheck, Award,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Cell as PieCell,
} from 'recharts'
import { useFinancesStats } from '@/api/queries'
import {
  FinanceKpiCard,
  FinanceChartCard,
  FinanceTable,
  FinancePageSkeleton,
} from '@/pages/finances/components'

const MONTH_NAMES = [
  'Janvier', 'Fevrier', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Aout', 'Septembre', 'Octobre', 'Novembre', 'Decembre',
]
const MONTHS_SHORT = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

interface MonthTableRow {
  month: number
  name: string
  revenue_cents: number
  invoices_paid: number
  invoices_overdue: number
}

export function RapportMensuelPage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1
  const [year, setYear] = useState(currentYear)
  const [selectedMonth, setSelectedMonth] = useState(currentMonth)

  const { data, isLoading, error: queryError, refetch } = useFinancesStats(year)

  const monthData = data?.monthly.find((m) => m.month === selectedMonth)
  const maxRevenue = data ? Math.max(...data.monthly.map((m) => m.revenue_cents), 1) : 1

  if (isLoading) return <FinancePageSkeleton />

  if (queryError) return (
    <div className="card text-center py-12">
      <p className="text-red-400 mb-4">Erreur lors du chargement du rapport.</p>
      <button onClick={() => refetch()} className="btn-secondary text-sm">Reessayer</button>
    </div>
  )

  if (!data) return <p className="text-dark-400">Aucune donnee disponible.</p>

  const miniChartData = data.monthly.map((m) => ({
    name: MONTHS_SHORT[m.month - 1],
    value: Math.round(m.revenue_cents / 100),
    month: m.month,
  }))

  const totalPaid = monthData ? monthData.invoices_paid : 0
  const totalOverdue = monthData ? monthData.invoices_overdue : 0
  const totalInvoices = totalPaid + totalOverdue
  const paymentRatio = totalInvoices > 0 ? totalPaid / totalInvoices : 0
  const donutData = [
    { name: 'Reglees', value: totalPaid, color: '#10b981' },
    { name: 'En retard', value: totalOverdue || 1, color: totalOverdue > 0 ? '#ef4444' : '#374151' },
  ]

  // Stacked bar chart data
  const stackedData = data.monthly.map((m) => ({
    name: MONTHS_SHORT[m.month - 1],
    month: m.month,
    paid: Math.round(m.revenue_cents / 100),
    overdue: m.invoices_overdue,
  }))

  const monthTableRows: MonthTableRow[] = data.monthly.map((m) => ({
    ...m,
    name: MONTH_NAMES[m.month - 1],
  }))

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <BarChart3 className="w-5 h-5 text-primary-400" />
        <PageHeader title="Rapport d'activite" />
        <div className="ml-auto flex items-center gap-4">
          {data && (
            <span className="text-xs text-dark-400">
              YTD : <span className="font-semibold">{formatCents(data.totals.revenue_ytd_cents)}</span>
            </span>
          )}
          <Link
            to="/finance/export"
            className="flex items-center gap-1.5 text-xs px-4 py-1.5 rounded-full border border-dark-600 text-dark-300 hover:border-primary-500 hover:text-primary-400"
          >
            <Download className="w-3.5 h-3.5" />
            Export
          </Link>
        </div>
      </div>

      {/* Selecteur annee + mois */}
      <div className="flex items-center justify-between gap-3">
        <button
          onClick={() => setYear((y) => y - 1)}
          className="p-2 rounded-lg hover:bg-dark-600 transition-colors"
        >
          <ChevronLeft className="w-4 h-4 text-dark-400" />
        </button>
        <span className="text-sm font-semibold">
          {MONTH_NAMES[selectedMonth - 1]} {year}
        </span>
        <button
          onClick={() => setYear((y) => y + 1)}
          disabled={year >= currentYear}
          className="p-2 rounded-lg hover:bg-dark-600 transition-colors disabled:opacity-30"
        >
          <ChevronRight className="w-4 h-4 text-dark-400" />
        </button>
      </div>

      {/* Sparkline annuel */}
      <FinanceChartCard title="Apercu annuel" subtitle="Cliquez sur un mois">
        <ResponsiveContainer width="100%" height={60}>
          <BarChart data={miniChartData} margin={{ top: 0, right: 4, left: 4, bottom: 0 }}>
            <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#6b7280' }} axisLine={false} tickLine={false} />
            <Tooltip
              formatter={((v: number) => [formatCents(v * 100), 'CA']) as never}
              contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 11 }}
            />
            <Bar
              dataKey="value"
              radius={[2, 2, 0, 0]}
              maxBarSize={20}
              onClick={(d) => setSelectedMonth(d.month as number)}
              cursor="pointer"
            >
              {miniChartData.map((entry) => (
                <Cell
                  key={entry.month}
                  fill={entry.month === selectedMonth ? '#8b5cf6' : 'rgba(139,92,246,0.25)'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </FinanceChartCard>

      {/* KPI du mois */}
      {monthData ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <FinanceKpiCard
            title="CA encaisse"
            value={formatCents(monthData.revenue_cents)}
            icon={<TrendingUp className="w-5 h-5" />}
            iconBg="bg-primary-500/10"
            iconColor="text-primary-400"
          />
          <FinanceKpiCard
            title="Factures payees"
            value={monthData.invoices_paid}
            icon={<FileCheck className="w-5 h-5" />}
            iconBg="bg-green-500/10"
            iconColor="text-green-400"
            valueClass="text-green-400"
          />
          <FinanceKpiCard
            title="En retard"
            value={monthData.invoices_overdue}
            icon={<AlertTriangle className="w-5 h-5" />}
            iconBg="bg-red-500/10"
            iconColor="text-red-400"
            valueClass={monthData.invoices_overdue > 0 ? 'text-red-400' : 'text-dark-300'}
          />
          <FinanceKpiCard
            title="Reservations actives"
            value={data.totals.active_reservations}
            icon={<CalendarCheck className="w-5 h-5" />}
            iconBg="bg-blue-500/10"
            iconColor="text-blue-400"
            valueClass="text-blue-400"
          />
        </div>
      ) : (
        <div className="card p-6 text-center">
          <p className="text-sm text-dark-400">Aucune donnee pour {MONTH_NAMES[selectedMonth - 1]} {year}</p>
        </div>
      )}

      {/* Evolution CA + Taux de recouvrement */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Evolution CA annuel */}
        <FinanceChartCard title="Evolution CA mensuel" subtitle={`${year}`}>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stackedData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#6b7280' }} axisLine={false} tickLine={false} />
              <YAxis
                tickFormatter={(v) => `${v}\u202F\u20AC`}
                tick={{ fontSize: 10, fill: '#6b7280' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                formatter={((v: number, name: string) => [
                  name === 'paid' ? formatCents(v * 100) : `${v} facture${v > 1 ? 's' : ''}`,
                  name === 'paid' ? 'CA' : 'En retard',
                ]) as never}
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 11 }}
              />
              <Bar
                dataKey="paid"
                name="CA"
                fill="#8b5cf6"
                radius={[3, 3, 0, 0]}
                maxBarSize={24}
                onClick={(d) => setSelectedMonth(d.month as number)}
                cursor="pointer"
              />
            </BarChart>
          </ResponsiveContainer>
        </FinanceChartCard>

        {/* Taux de recouvrement */}
        {monthData && (
          <FinanceChartCard
            title="Taux de reglement"
            subtitle={`${MONTH_NAMES[selectedMonth - 1]} ${year}`}
          >
            <div className="flex items-center justify-center gap-6">
              <ResponsiveContainer width={140} height={140}>
                <PieChart>
                  <Pie
                    data={donutData}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={60}
                    dataKey="value"
                    paddingAngle={2}
                  >
                    {donutData.map((entry) => (
                      <PieCell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-3 text-sm">
                <div>
                  <p className="text-2xl font-bold text-dark-50">{Math.round(paymentRatio * 100)}%</p>
                  <p className="text-xs text-dark-400">Taux de reglement</p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
                  <span className="text-dark-300">{totalPaid} reglees</span>
                </div>
                {totalOverdue > 0 && (
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
                    <span className="text-red-400">{totalOverdue} en retard</span>
                  </div>
                )}
              </div>
            </div>
          </FinanceChartCard>
        )}
      </div>

      {/* Recapitulatif annuel */}
      <FinanceTable<MonthTableRow>
        title={`Recapitulatif ${year}`}
        keyExtractor={(row) => row.month}
        data={monthTableRows}
        onRowClick={(row) => setSelectedMonth(row.month)}
        columns={[
          {
            key: 'name',
            label: 'Mois',
            render: (row) => (
              <span className={cn('font-medium', row.month === selectedMonth && 'text-primary-400')}>
                {row.name}
              </span>
            ),
          },
          {
            key: 'revenue',
            label: 'CA encaisse',
            align: 'right',
            render: (row) => <span className="tabular-nums">{formatCents(row.revenue_cents)}</span>,
          },
          {
            key: 'paid',
            label: 'Payees',
            align: 'right',
            render: (row) => <span className="tabular-nums text-green-400">{row.invoices_paid}</span>,
          },
          {
            key: 'overdue',
            label: 'Retard',
            align: 'right',
            render: (row) => (
              <span className={cn('tabular-nums', row.invoices_overdue > 0 ? 'text-red-400' : 'text-dark-400')}>
                {row.invoices_overdue}
              </span>
            ),
          },
        ]}
        footer={
          <div className="flex justify-between text-sm font-semibold px-0">
            <span className="text-dark-400">Total {year}</span>
            <div className="flex gap-8">
              <span>{formatCents(data.totals.revenue_ytd_cents)}</span>
              <span className="text-green-400">{data.monthly.reduce((s, m) => s + m.invoices_paid, 0)}</span>
              <span className="text-red-400">{data.monthly.reduce((s, m) => s + m.invoices_overdue, 0)}</span>
            </div>
          </div>
        }
      />
    </div>
  )
}
