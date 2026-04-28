import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useAnalyticsKpis } from '@/api/queries'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { formatCents } from '@/lib/utils'
import type { TopProductItem, SeasonalityMonthly } from '@/types/dashboard'
import {
  ShoppingCart,
  TrendingUp,
  BarChart3,
  Package,
  Calendar,
  ArrowRight,
} from 'lucide-react'

const PERIOD_OPTIONS = [
  { label: '30 j', days: 30 },
  { label: '90 j', days: 90 },
  { label: '1 an', days: 365 },
  { label: '3 ans', days: 1095 },
] as const

const MONTH_LABELS = [
  'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
  'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc',
]

const YEAR_COLORS = [
  'bg-dark-500',
  'bg-primary-400',
  'bg-gold-400',
] as const

// ── Skeleton ──────────────────────────────────────────────────────────────────

function AnalyticsSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 skel rounded w-56" />
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="card p-6 space-y-3">
            <div className="h-3 skel rounded w-24" />
            <div className="h-8 skel rounded w-20" />
          </div>
        ))}
      </div>
      <div className="card p-4 space-y-3">
        <div className="h-4 skel rounded w-40" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-10 skel rounded" />
        ))}
      </div>
    </div>
  )
}

// ── KPI Card ──────────────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
  color = 'text-white',
}: {
  label: string
  value: string | number
  sub?: string
  icon: React.ElementType
  color?: string
}) {
  return (
    <div className="card p-6 flex items-start gap-4">
      <div className="p-2.5 card rounded-lg">
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <div className="min-w-0">
        <p className="text-sm text-dark-400">{label}</p>
        <p className={`text-2xl font-bold mt-0.5 ${color}`}>{value}</p>
        {sub && <p className="text-xs text-dark-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

// ── Utilization gauge ─────────────────────────────────────────────────────────

function UtilizationGauge({ rate, rented, total }: { rate: number; rented: number; total: number }) {
  const color = rate > 80 ? 'bg-orange-400' : rate > 50 ? 'bg-primary-400' : 'bg-green-400'
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-primary-400" />
          <span className="text-sm text-dark-400">Taux d'utilisation</span>
        </div>
        <span className="text-2xl font-bold">{rate} %</span>
      </div>
      <div className="h-3 bg-dark-900 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${Math.min(rate, 100)}%` }} />
      </div>
      <p className="text-xs text-dark-500 mt-2">{rented} en location / {total} total</p>
    </div>
  )
}

// ── Top products ──────────────────────────────────────────────────────────────

function TopProductsTable({ products }: { products: TopProductItem[] }) {
  const navigate = useNavigate()
  if (!products.length) {
    return (
      <div className="card p-8 text-center text-dark-400">
        <Package className="w-10 h-10 text-dark-600 mx-auto mb-2" />
        Aucune donnee de location sur cette periode
      </div>
    )
  }
  const maxCount = products[0]?.rental_count ?? 1
  return (
    <div className="card">
      <div className="p-4 border-b border-dark-600 flex items-center gap-2">
        <BarChart3 className="w-4 h-4 text-dark-400" />
        <h2 className="font-medium">Top 10 produits les plus loues</h2>
      </div>
      <div className="divide-y divide-dark-600">
        {products.map((p, idx) => {
          const barWidth = maxCount > 0 ? (p.rental_count / maxCount) * 100 : 0
          return (
            <button
              key={p.product_id}
              className="w-full p-4 flex items-center gap-4 hover:bg-dark-600/30 transition-colors text-left"
              onClick={() => navigate({ to: '/catalogue/products/$id', params: { id: String(p.product_id) } })}
            >
              <span className="w-6 text-center text-sm font-bold text-dark-400">{idx + 1}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{p.product_name}</p>
                <div className="flex items-center gap-3 mt-1">
                  {p.category && <span className="text-xs text-dark-500">{p.category}</span>}
                  <span className="text-xs text-dark-400">{p.rental_count} location{p.rental_count > 1 ? 's' : ''}</span>
                  <span className="text-xs text-dark-500">{p.total_quantity} unites</span>
                </div>
                <div className="h-1 bg-dark-900 rounded-full mt-2 overflow-hidden">
                  <div className="h-full bg-primary-500 rounded-full" style={{ width: `${barWidth}%` }} />
                </div>
              </div>
              <div className="text-right shrink-0">
                <p className="text-sm font-bold text-gold-400">{formatCents(p.revenue_cents)}</p>
              </div>
              <ArrowRight className="w-4 h-4 text-dark-500 shrink-0" />
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Seasonality chart (mini bar chart en CSS) ─────────────────────────────────

function SeasonalityChart({ data, years }: { data: SeasonalityMonthly[]; years: number[] }) {
  if (!data.length) return null

  // Build a map: year -> month -> revenue_cents
  const byYearMonth: Record<number, Record<number, number>> = {}
  for (const y of years) byYearMonth[y] = {}
  for (const d of data) {
    if (!byYearMonth[d.year]) byYearMonth[d.year] = {}
    byYearMonth[d.year][d.month] = d.revenue_cents
  }

  const maxRevenue = Math.max(...data.map((d) => d.revenue_cents), 1)

  return (
    <div className="card">
      <div className="p-4 border-b border-dark-600 flex items-center gap-2">
        <Calendar className="w-4 h-4 text-dark-400" />
        <h2 className="font-medium">Saisonnalite (CA mensuel)</h2>
      </div>
      <div className="p-4">
        {/* Legend */}
        <div className="flex items-center gap-4 mb-4">
          {years.map((y, i) => (
            <div key={y} className="flex items-center gap-1.5">
              <div className={`w-3 h-3 rounded-sm ${YEAR_COLORS[i]}`} />
              <span className="text-xs text-dark-400">{y}</span>
            </div>
          ))}
        </div>
        {/* Bars */}
        <div className="flex items-end gap-1 h-40">
          {Array.from({ length: 12 }).map((_, m) => {
            const month = m + 1
            return (
              <div key={month} className="flex-1 flex flex-col items-center gap-0.5">
                <div className="w-full flex items-end justify-center gap-px h-32">
                  {years.map((y, i) => {
                    const val = byYearMonth[y]?.[month] ?? 0
                    const h = maxRevenue > 0 ? (val / maxRevenue) * 100 : 0
                    return (
                      <div
                        key={y}
                        className={`flex-1 max-w-3 rounded-t ${YEAR_COLORS[i]} transition-all`}
                        style={{ height: `${Math.max(h, 1)}%` }}
                        title={`${MONTH_LABELS[m]} ${y}: ${formatCents(val)}`}
                      />
                    )
                  })}
                </div>
                <span className="text-[10px] text-dark-500">{MONTH_LABELS[m]}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [periodDays, setPeriodDays] = useState(365)
  const { data, isLoading, error, refetch } = useAnalyticsKpis(periodDays)

  if (isLoading || (!data && !error)) return <AnalyticsSkeleton />
  if (error || !data) return <ErrorState onRetry={() => refetch()} />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-primary-400" />
            Statistiques
          </h1>
          <p className="text-dark-400 mt-1">KPIs, top produits, saisonnalite</p>
        </div>
        <div className="flex gap-1 bg-dark-900 rounded-lg p-1">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              onClick={() => setPeriodDays(opt.days)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                periodDays === opt.days
                  ? 'bg-primary-500 text-white'
                  : 'text-dark-400 hover:text-white'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPIs principaux */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <KpiCard
          label="Panier moyen"
          value={formatCents(data.avg_basket_cents)}
          sub={`Sur ${data.total_reservations} reservation${data.total_reservations > 1 ? 's' : ''}`}
          icon={ShoppingCart}
          color="text-gold-400"
        />
        <KpiCard
          label="CA total"
          value={formatCents(data.total_revenue_cents)}
          sub={`${data.total_reservations} reservation${data.total_reservations > 1 ? 's' : ''}`}
          icon={TrendingUp}
          color="text-primary-400"
        />
        <UtilizationGauge
          rate={data.utilization_rate}
          rented={data.total_rented}
          total={data.total_stock}
        />
      </div>

      {/* Top produits */}
      <TopProductsTable products={data.top_products} />

      {/* Saisonnalite */}
      <SeasonalityChart data={data.monthly_revenue} years={data.seasonality_years} />
    </div>
  )
}
