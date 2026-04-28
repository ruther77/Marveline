// Route : /_app/etl-dashboard
// Dashboard analytique ETL — KPIs, tendance, stats, top 5 à corriger

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { BarChart3, AlertTriangle, Clock, TrendingUp, ArrowLeft, DollarSign } from 'lucide-react'
import { getDashboard, getQualityMetrics, listImports } from '@/api/etl_imports'
import type { DashboardVendorStats, DashboardQualityTrend, QualityMetricsVendor } from '@/api/etl_imports'
import { formatCents, STATUT_COLORS, STATUT_LABELS } from '@/utils/etl-helpers'

// ─── Types ──────────────────────────────────────────────────────────────────

type Period = 'week' | 'month' | 'all'

const PERIOD_LABELS: Record<Period, string> = {
  week: 'Cette semaine',
  month: 'Ce mois',
  all: 'Tout',
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatTime(sec: number | null): string {
  if (!sec) return '—'
  if (sec < 60) return `${Math.round(sec)}s`
  if (sec < 3600) return `${Math.round(sec / 60)}min`
  return `${(sec / 3600).toFixed(1)}h`
}

function isInPeriod(dateStr: string, period: Period): boolean {
  if (period === 'all') return true
  const d = new Date(dateStr)
  const now = new Date()
  if (period === 'month') return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()
  // week
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
  return d >= weekAgo
}

// ─── Components ─────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string; sub?: string; icon: typeof BarChart3; color: string
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${color}`}>
          <Icon className="h-4 w-4 text-white" />
        </div>
        <span className="text-[11px] text-slate-500 font-medium">{label}</span>
      </div>
      <div className="text-2xl font-bold text-slate-900 leading-none">{value}</div>
      {sub && <div className="text-[11px] text-slate-400 mt-1">{sub}</div>}
    </div>
  )
}

function QualityBar({ score }: { score: number | null }) {
  const pct = score ?? 0
  const color = pct >= 80 ? 'bg-emerald-500' : pct >= 60 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] font-mono text-slate-600 w-8 text-right">{pct}</span>
    </div>
  )
}

function TrendChart({ data }: { data: DashboardQualityTrend[] }) {
  if (data.length === 0) return <p className="text-[12px] text-slate-400 text-center py-8">Pas encore de données</p>

  const reversed = [...data].reverse()
  const maxScore = 100
  const barWidth = Math.max(4, Math.min(16, 400 / reversed.length))

  return (
    <div className="relative">
      {/* Y-axis labels */}
      <div className="absolute left-0 top-0 bottom-4 flex flex-col justify-between text-[9px] text-slate-400 w-6">
        <span>100</span>
        <span>50</span>
        <span>0</span>
      </div>
      {/* Chart */}
      <div className="ml-8 flex items-end gap-[2px] h-36">
        {reversed.map((d, i) => {
          const pct = ((d.quality_score ?? 0) / maxScore) * 100
          const color = d.vendor_code === 'METRO' ? 'bg-emerald-500' : 'bg-amber-500'
          return (
            <div key={d.id} className="flex flex-col items-center justify-end h-full group relative"
              style={{ width: barWidth }}>
              <div className={`w-full rounded-t ${color} transition-all hover:opacity-80`}
                style={{ height: `${pct}%`, minHeight: 2 }} />
              {/* Tooltip */}
              <div className="absolute bottom-full mb-1 hidden group-hover:block bg-slate-800 text-white text-[10px] px-2 py-1 rounded whitespace-nowrap z-10">
                {d.vendor_code} · Q:{d.quality_score} · #{d.id}
              </div>
            </div>
          )
        })}
      </div>
      {/* X-axis */}
      <div className="ml-8 flex justify-between text-[9px] text-slate-400 mt-1">
        <span>ancien</span>
        <span>récent</span>
      </div>
    </div>
  )
}

function QualityCell({ pct }: { pct: number }) {
  const color = pct >= 80 ? 'bg-emerald-100 text-emerald-700'
    : pct >= 50 ? 'bg-amber-100 text-amber-700'
    : 'bg-red-100 text-red-700'
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold ${color}`}>
      {pct.toFixed(0)}%
    </span>
  )
}

function QualityMetricsTable({ vendors }: { vendors: QualityMetricsVendor[] }) {
  if (vendors.length === 0) {
    return <p className="text-[12px] text-slate-400 text-center py-4">Aucun import sur la période.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px]">
        <thead>
          <tr className="text-slate-400 border-b border-slate-100">
            <th className="text-left py-1.5 font-medium">Fournisseur</th>
            <th className="text-right py-1.5 font-medium" title="Nombre total de lignes agrégées">Lignes</th>
            <th className="text-center py-1.5 font-medium" title="Confiance ≥ 60/100">Conf.</th>
            <th className="text-center py-1.5 font-medium">EAN</th>
            <th className="text-center py-1.5 font-medium">Marque</th>
            <th className="text-center py-1.5 font-medium" title="Catégorie hors AUTRE">Cat.</th>
            <th className="text-center py-1.5 font-medium">Cond.</th>
            <th className="text-center py-1.5 font-medium">Vol.</th>
            <th className="text-center py-1.5 font-medium">Prix</th>
            <th className="text-center py-1.5 font-medium">TVA</th>
          </tr>
        </thead>
        <tbody>
          {vendors.map(v => (
            <tr key={v.vendor_code} className="border-b border-slate-50">
              <td className="py-1.5 font-semibold text-slate-800">
                {v.vendor_code}
                <span className="text-slate-400 font-normal ml-1">({v.nb_imports})</span>
              </td>
              <td className="py-1.5 text-right font-mono text-slate-600">{v.nb_lignes}</td>
              <td className="py-1.5 text-center"><QualityCell pct={v.pct_confidence_ok} /></td>
              <td className="py-1.5 text-center"><QualityCell pct={v.pct_ean} /></td>
              <td className="py-1.5 text-center"><QualityCell pct={v.pct_marque} /></td>
              <td className="py-1.5 text-center"><QualityCell pct={v.pct_categorie} /></td>
              <td className="py-1.5 text-center"><QualityCell pct={v.pct_conditionnement} /></td>
              <td className="py-1.5 text-center"><QualityCell pct={v.pct_volume} /></td>
              <td className="py-1.5 text-center"><QualityCell pct={v.pct_prix} /></td>
              <td className="py-1.5 text-center"><QualityCell pct={v.pct_tva} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function VendorTable({ vendors }: { vendors: DashboardVendorStats[] }) {
  return (
    <table className="w-full text-[12px]">
      <thead>
        <tr className="text-slate-400 border-b border-slate-100">
          <th className="text-left py-2 font-medium">Fournisseur</th>
          <th className="text-right py-2 font-medium">Imports</th>
          <th className="text-right py-2 font-medium">Score moyen</th>
        </tr>
      </thead>
      <tbody>
        {vendors.map(v => (
          <tr key={v.vendor_code} className="border-b border-slate-50">
            <td className="py-2 font-semibold text-slate-800">{v.vendor_code}</td>
            <td className="py-2 text-right text-slate-600">{v.total_imports}</td>
            <td className="py-2 text-right"><QualityBar score={v.avg_quality} /></td>
          </tr>
        ))}
        {vendors.length === 0 && (
          <tr><td colSpan={3} className="py-4 text-center text-slate-400">Aucun fournisseur</td></tr>
        )}
      </tbody>
    </table>
  )
}

// ─── Page ───────────────────────────────────────────────────────────────────

export default function EtlDashboardPage() {
  const [period, setPeriod] = useState<Period>('month')

  const { data, isLoading } = useQuery({
    queryKey: ['etl-dashboard'],
    queryFn: getDashboard,
    staleTime: 60_000,
  })

  // Imports pour le volume € et le top 5
  const { data: importsData } = useQuery({
    queryKey: ['etl-imports', 'all'],
    queryFn: () => listImports('all', 200, 0),
    staleTime: 60_000,
  })

  // Qualité par fournisseur (taux remplissage attribut sur 90j)
  const { data: quality } = useQuery({
    queryKey: ['etl-quality-metrics', 90],
    queryFn: () => getQualityMetrics(90),
    staleTime: 5 * 60_000,
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-4 animate-pulse">
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => <div key={i} className="bg-slate-100 rounded-xl h-24" />)}
        </div>
        <div className="bg-slate-100 rounded-xl h-48" />
        <div className="bg-slate-100 rounded-xl h-40" />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center">
          <div className="text-4xl mb-3">📊</div>
          <p className="text-slate-500">Aucune donnée disponible. Importez des factures pour voir les statistiques.</p>
        </div>
      </div>
    )
  }

  const d = data
  const previewCount = (d.by_status ?? {})['PREVIEW'] ?? 0
  const allImports = importsData?.items ?? []

  // Filtered imports by period
  const periodImports = allImports.filter(i => isInPeriod(i.created_at, period))
  const volumeHt = periodImports.reduce((s, i) => s + (i.montant_ht_total ?? 0), 0)

  // Top 5 worst imports (lowest quality, PREVIEW only)
  const worstImports = [...allImports]
    .filter(i => i.statut === 'PREVIEW')
    .sort((a, b) => (a.quality_score ?? 100) - (b.quality_score ?? 100))
    .slice(0, 5)

  return (
    <div className="p-6 space-y-5 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/etl-imports" className="text-slate-400 hover:text-slate-600"><ArrowLeft className="h-5 w-5" /></Link>
          <h1 className="text-xl font-bold text-slate-900">Tableau de bord ETL</h1>
        </div>
        <div className="flex items-center gap-2">
          {/* Period selector */}
          <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5">
            {(Object.keys(PERIOD_LABELS) as Period[]).map(p => (
              <button key={p} onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                  period === p ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                }`}>
                {PERIOD_LABELS[p]}
              </button>
            ))}
          </div>
          {previewCount > 0 && (
            <Link to="/etl-imports" className="text-[12px] font-semibold text-amber-600 bg-amber-50 px-3 py-1.5 rounded-lg hover:bg-amber-100">
              {previewCount} à valider
            </Link>
          )}
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <KpiCard label="Total imports" value={String(d.total_imports)} icon={BarChart3} color="bg-slate-700" />
        <KpiCard label="Score moyen" value={d.avg_quality_global ? `${d.avg_quality_global}` : '—'} sub="sur 100" icon={TrendingUp} color="bg-emerald-600" />
        <KpiCard label="Conflits en attente" value={String(d.pending_conflicts)} icon={AlertTriangle} color={d.pending_conflicts > 0 ? 'bg-amber-500' : 'bg-slate-400'} />
        <KpiCard label="Temps moyen" value={formatTime(d.avg_correction_time_sec)} sub="correction" icon={Clock} color="bg-violet-600" />
        <KpiCard label={`Volume HT (${PERIOD_LABELS[period].toLowerCase()})`} value={formatCents(volumeHt)} icon={DollarSign} color="bg-blue-600" />
      </div>

      {/* Trend + Top 5 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Trend */}
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <h2 className="text-[13px] font-semibold text-slate-800 mb-3">Tendance qualité (30 derniers)</h2>
          <TrendChart data={d.quality_trend} />
          <div className="flex gap-4 mt-2 text-[10px] text-slate-400">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> METRO</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> TAIYAT</span>
          </div>
        </div>

        {/* Top 5 worst */}
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <h2 className="text-[13px] font-semibold text-slate-800 mb-3">Imports à corriger en priorité</h2>
          {worstImports.length === 0 ? (
            <div className="py-6 text-center">
              <div className="text-3xl mb-2">✅</div>
              <p className="text-[12px] text-slate-400">Tous les imports sont validés</p>
            </div>
          ) : (
            <div className="space-y-2">
              {worstImports.map(imp => (
                <Link key={imp.id} to="/etl-imports/$id" params={{ id: String(imp.id) }}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 transition-colors">
                  <span className={`text-xs font-bold ${
                    (imp.quality_score ?? 0) >= 80 ? 'text-green-600' : (imp.quality_score ?? 0) >= 50 ? 'text-amber-600' : 'text-red-600'
                  }`}>
                    Q:{imp.quality_score ?? 0}
                  </span>
                  <span className="text-sm text-slate-700 flex-1 truncate">
                    {imp.numero_facture || imp.fichier_source || `#${imp.id}`}
                  </span>
                  <span className="text-xs text-slate-400">{imp.nb_lignes_total} lignes</span>
                  <span className="text-slate-300">→</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Stats fournisseurs + Statuts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <h2 className="text-[13px] font-semibold text-slate-800 mb-3">Par fournisseur</h2>
          <VendorTable vendors={d.vendor_stats} />
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <h2 className="text-[13px] font-semibold text-slate-800 mb-3">Répartition par statut</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(d.by_status ?? {}).map(([status, count]) => (
              <span key={status} className={`px-3 py-1.5 rounded-full text-[11px] font-medium ${STATUT_COLORS[status] || 'bg-slate-100 text-slate-600'}`}>
                {STATUT_LABELS[status] || status} <strong>{count}</strong>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Qualité d'enrichissement par fournisseur */}
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[13px] font-semibold text-slate-800">Qualité d'enrichissement par fournisseur</h2>
          <span className="text-[10px] text-slate-400">Sur {quality?.days ?? 90} derniers jours</span>
        </div>
        <QualityMetricsTable vendors={quality?.vendors ?? []} />
        <p className="mt-2 text-[10px] text-slate-400">
          % de lignes où l'attribut est rempli. Un fournisseur sous-performant sur <em>Cond.</em> ou <em>Marque</em>
          signale un parser minimal (ex : Excel sans colonnes structurées).
        </p>
      </div>
    </div>
  )
}
