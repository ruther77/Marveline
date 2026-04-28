import { PageHeader } from '@/components/PageHeader'
import { useState, useMemo } from 'react'
import { useQueries } from '@tanstack/react-query'
import { normalizeError } from '@shared/errors/normalizer'
import { useInvoiceTvaReport } from '@/api/queries/useInvoices'
import { invoicesApi } from '@/api/invoices'
import { formatCents, cn } from '@/lib/utils'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { FileText, Euro, Receipt, ChevronLeft, ChevronRight } from 'lucide-react'
import {
  FinanceKpiCard,
  FinanceChartCard,
  FinanceTable,
  FinanceKpiSkeleton,
  FinancePageSkeleton,
} from '@/pages/finances/components'
import type { TvaBreakdownItem } from '@/types/invoice'

type PeriodMode = 'monthly' | 'quarterly' | 'yearly'

const MONTH_NAMES = [
  'Janvier', 'Fevrier', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Aout', 'Septembre', 'Octobre', 'Novembre', 'Decembre',
]
const QUARTER_LABELS = ['T1 (Jan-Mar)', 'T2 (Avr-Jun)', 'T3 (Jul-Sep)', 'T4 (Oct-Dec)']
const QUARTER_MONTHS: number[][] = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]

function monthKey(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}`
}

function aggregateBreakdowns(reports: { breakdown_by_rate: TvaBreakdownItem[] }[]): {
  invoice_count: number
  total_base_ht_cents: number
  total_tva_cents: number
  total_ttc_cents: number
  breakdown_by_rate: TvaBreakdownItem[]
} {
  let invoice_count = 0
  let total_base_ht_cents = 0
  let total_tva_cents = 0
  let total_ttc_cents = 0
  const byRate = new Map<number, TvaBreakdownItem>()

  for (const r of reports) {
    const rep = r as { invoice_count?: number; total_base_ht_cents?: number; total_tva_cents?: number; total_ttc_cents?: number; breakdown_by_rate: TvaBreakdownItem[] }
    invoice_count += rep.invoice_count ?? 0
    total_base_ht_cents += rep.total_base_ht_cents ?? 0
    total_tva_cents += rep.total_tva_cents ?? 0
    total_ttc_cents += rep.total_ttc_cents ?? 0
    for (const br of rep.breakdown_by_rate) {
      const existing = byRate.get(br.rate)
      if (existing) {
        existing.base_ht_cents += br.base_ht_cents
        existing.tva_cents += br.tva_cents
        existing.ttc_cents += br.ttc_cents
      } else {
        byRate.set(br.rate, { ...br })
      }
    }
  }
  return {
    invoice_count, total_base_ht_cents, total_tva_cents, total_ttc_cents,
    breakdown_by_rate: Array.from(byRate.values()).sort((a, b) => a.rate - b.rate),
  }
}

function TvaContent({ report }: {
  report: {
    invoice_count: number
    total_base_ht_cents: number
    total_tva_cents: number
    total_ttc_cents: number
    breakdown_by_rate: TvaBreakdownItem[]
  }
}) {
  const chartData = report.breakdown_by_rate.map((row) => ({
    name: `${Math.round(row.rate * 1000) / 10}%`,
    tva: Math.round(row.tva_cents / 100),
    ht: Math.round(row.base_ht_cents / 100),
  }))

  return (
    <>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <FinanceKpiCard
          title="Factures incluses"
          value={report.invoice_count}
          icon={<FileText className="w-5 h-5" />}
          iconBg="bg-primary-500/10"
          iconColor="text-primary-400"
          compact
        />
        <FinanceKpiCard
          title="Base HT totale"
          value={formatCents(report.total_base_ht_cents)}
          icon={<Euro className="w-5 h-5" />}
          iconBg="bg-green-500/10"
          iconColor="text-green-400"
          compact
        />
        <FinanceKpiCard
          title="TVA collectee"
          value={formatCents(report.total_tva_cents)}
          icon={<Receipt className="w-5 h-5" />}
          iconBg="bg-amber-500/10"
          iconColor="text-amber-400"
          valueClass="text-primary-400"
          compact
        />
      </div>

      {report.breakdown_by_rate.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <FinanceChartCard title="TVA par taux" subtitle="HT vs TVA">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 16, left: 40, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#374151" />
                <XAxis
                  type="number"
                  tickFormatter={(v) => `${v}\u202F\u20AC`}
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#6b7280' }} />
                <Tooltip
                  formatter={((v: number, name: string) => [
                    formatCents(v * 100),
                    name === 'ht' ? 'Base HT' : 'TVA',
                  ]) as never}
                  contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
                />
                <Bar dataKey="ht" name="Base HT" fill="#3b82f6" radius={[0, 4, 4, 0]} maxBarSize={20} />
                <Bar dataKey="tva" name="TVA" fill="#f59e0b" radius={[0, 4, 4, 0]} maxBarSize={20} />
              </BarChart>
            </ResponsiveContainer>
          </FinanceChartCard>

          <FinanceTable<TvaBreakdownItem>
            title="Detail par taux"
            keyExtractor={(row) => row.rate}
            data={report.breakdown_by_rate}
            columns={[
              {
                key: 'rate',
                label: 'Taux',
                render: (row) => <span className="font-medium">{Math.round(row.rate * 1000) / 10} %</span>,
              },
              {
                key: 'base_ht',
                label: 'Base HT',
                align: 'right',
                render: (row) => <span className="tabular-nums">{formatCents(row.base_ht_cents)}</span>,
              },
              {
                key: 'tva',
                label: 'TVA',
                align: 'right',
                render: (row) => <span className="tabular-nums text-primary-400">{formatCents(row.tva_cents)}</span>,
              },
              {
                key: 'ttc',
                label: 'TTC',
                align: 'right',
                render: (row) => <span className="tabular-nums font-medium">{formatCents(row.ttc_cents)}</span>,
              },
            ]}
            footer={
              <div className="flex justify-between text-sm font-semibold">
                <span>Total</span>
                <div className="flex gap-6">
                  <span>{formatCents(report.total_base_ht_cents)}</span>
                  <span className="text-primary-400">{formatCents(report.total_tva_cents)}</span>
                  <span>{formatCents(report.total_ttc_cents)}</span>
                </div>
              </div>
            }
          />
        </div>
      ) : (
        <p className="text-dark-400 text-sm">Aucune facture pour cette période.</p>
      )}
    </>
  )
}

export function TvaReportPage() {
  const today = new Date()
  const [mode, setMode] = useState<PeriodMode>('monthly')
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth() + 1)
  const [quarter, setQuarter] = useState(Math.floor(today.getMonth() / 3))

  // Monthly mode — single query
  const monthStr = monthKey(year, month)
  const monthlyQuery = useInvoiceTvaReport(mode === 'monthly' ? monthStr : null)

  // Quarterly mode — 3 parallel queries
  const quarterMonths = QUARTER_MONTHS[quarter]
  const quarterQueries = useQueries({
    queries: (mode === 'quarterly' ? quarterMonths : []).map((m) => ({
      queryKey: ['invoices', 'tva-report', monthKey(year, m)],
      queryFn: () => invoicesApi.getTvaReport(monthKey(year, m)),
      staleTime: 5 * 60 * 1000,
    })),
  })

  // Yearly mode — 12 parallel queries
  const yearQueries = useQueries({
    queries: (mode === 'yearly' ? Array.from({ length: 12 }, (_, i) => i + 1) : []).map((m) => ({
      queryKey: ['invoices', 'tva-report', monthKey(year, m)],
      queryFn: () => invoicesApi.getTvaReport(monthKey(year, m)),
      staleTime: 5 * 60 * 1000,
    })),
  })

  const isLoading =
    (mode === 'monthly' && monthlyQuery.isLoading) ||
    (mode === 'quarterly' && quarterQueries.some((q) => q.isLoading)) ||
    (mode === 'yearly' && yearQueries.some((q) => q.isLoading))

  const error =
    (mode === 'monthly' && monthlyQuery.error) ||
    (mode === 'quarterly' && quarterQueries.find((q) => q.error)?.error) ||
    (mode === 'yearly' && yearQueries.find((q) => q.error)?.error)

  const aggregated = useMemo(() => {
    if (mode === 'monthly') return monthlyQuery.data ?? null
    if (mode === 'quarterly') {
      const ready = quarterQueries.filter((q) => q.data)
      if (ready.length === 0) return null
      return aggregateBreakdowns(ready.map((q) => q.data!))
    }
    const ready = yearQueries.filter((q) => q.data)
    if (ready.length === 0) return null
    return aggregateBreakdowns(ready.map((q) => q.data!))
  }, [mode, monthlyQuery.data, quarterQueries, yearQueries])

  const periodLabel =
    mode === 'monthly' ? `${MONTH_NAMES[month - 1]} ${year}` :
    mode === 'quarterly' ? `${QUARTER_LABELS[quarter]} ${year}` :
    `Annee ${year}`

  function navigatePrev() {
    if (mode === 'monthly') {
      if (month === 1) { setMonth(12); setYear((y) => y - 1) }
      else setMonth((m) => m - 1)
    } else if (mode === 'quarterly') {
      if (quarter === 0) { setQuarter(3); setYear((y) => y - 1) }
      else setQuarter((q) => q - 1)
    } else {
      setYear((y) => y - 1)
    }
  }

  function navigateNext() {
    if (mode === 'monthly') {
      if (month === 12) { setMonth(1); setYear((y) => y + 1) }
      else setMonth((m) => m + 1)
    } else if (mode === 'quarterly') {
      if (quarter === 3) { setQuarter(0); setYear((y) => y + 1) }
      else setQuarter((q) => q + 1)
    } else {
      setYear((y) => y + 1)
    }
  }

  const canNext =
    mode === 'monthly' ? !(year === today.getFullYear() && month >= today.getMonth() + 1) :
    mode === 'quarterly' ? !(year === today.getFullYear() && quarter >= Math.floor(today.getMonth() / 3)) :
    year < today.getFullYear()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <PageHeader title="Rapport TVA" subtitle="Factures encaissees uniquement" />

        {/* Mode toggle */}
        <div className="flex rounded-lg border border-[var(--border)] overflow-hidden">
          {(['monthly', 'quarterly', 'yearly'] as PeriodMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium transition-colors',
                mode === m
                  ? 'bg-primary-500 text-white'
                  : 'bg-[var(--s2)] text-[var(--muted)] hover:bg-[var(--s3)]'
              )}
            >
              {m === 'monthly' ? 'Mensuel' : m === 'quarterly' ? 'Trimestriel' : 'Annuel'}
            </button>
          ))}
        </div>
      </div>

      {/* Selecteur période */}
      <div className="flex items-center justify-center gap-4">
        <button
          onClick={navigatePrev}
          className="p-2 rounded-lg hover:bg-dark-600 transition-colors"
        >
          <ChevronLeft className="w-4 h-4 text-dark-400" />
        </button>
        <span className="text-sm font-semibold min-w-[180px] text-center">{periodLabel}</span>
        <button
          onClick={navigateNext}
          disabled={!canNext}
          className="p-2 rounded-lg hover:bg-dark-600 transition-colors disabled:opacity-30"
        >
          <ChevronRight className="w-4 h-4 text-dark-400" />
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {normalizeError(error).message || 'Erreur lors du chargement du rapport'}
        </div>
      )}

      {/* Loading */}
      {isLoading && <FinanceKpiSkeleton count={3} />}
      {isLoading && <FinancePageSkeleton />}

      {/* Content */}
      {!isLoading && !error && aggregated && <TvaContent report={aggregated} />}

      {!isLoading && !error && !aggregated && (
        <p className="text-dark-400 text-sm text-center py-8">Aucune donnee pour cette période.</p>
      )}
    </div>
  )
}
