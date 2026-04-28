import { useState } from 'react'
import { useDashboardExportCsv, useFinancesStats } from '@/api/queries/useDashboard'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents } from '@/lib/utils'
import { Download, FileText, CheckCircle, Loader2, Euro, AlertTriangle, Calendar } from 'lucide-react'
import { FinanceKpiCard, FinanceKpiSkeleton } from '@/pages/finances/components'

const CURRENT_YEAR = new Date().getFullYear()
const YEAR_OPTIONS = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2]

export default function FinancesExportPage() {
  const [year, setYear] = useState(CURRENT_YEAR)
  const [exported, setExported] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const exportCsv = useDashboardExportCsv()

  const { data, isLoading, error } = useFinancesStats(year)

  const handleExportCsv = async () => {
    if (exportCsv.isPending) return
    setExportError(null)
    setExported(false)
    try {
      const blob = await exportCsv.mutateAsync(year)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `rapport-financier-${year}.csv`
      a.click()
      URL.revokeObjectURL(url)
      setExported(true)
    } catch (err) {
      setExportError(normalizeError(err).message || "Erreur lors de l'export")
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
        <div className="h-10 w-32 bg-dark-800 rounded-lg animate-pulse" />
        <FinanceKpiSkeleton count={3} />
        <div className="card p-6 animate-pulse">
          <div className="h-4 bg-dark-700 rounded w-36 mb-4" />
          <div className="h-16 bg-dark-700 rounded" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto">
        <div className="card p-8 text-center text-red-400">
          {error ? normalizeError(error).message : 'Données indisponibles'}
        </div>
      </div>
    )
  }

  const { monthly, totals } = data
  const monthsWithData = monthly.filter((m) => m.revenue_cents > 0).length

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <select
          className="input"
          value={year}
          onChange={(e) => { setYear(Number(e.target.value)); setExported(false); setExportError(null) }}
        >
          {YEAR_OPTIONS.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
        <h1 className="text-lg font-semibold">Export financier {year}</h1>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <FinanceKpiCard
          title="CA annuel"
          value={formatCents(totals.revenue_ytd_cents)}
          icon={<Euro className="w-5 h-5" />}
          iconBg="bg-primary-500/10"
          iconColor="text-primary-400"
          compact
        />
        <FinanceKpiCard
          title="Impayés"
          value={formatCents(totals.overdue_amount_cents)}
          icon={<AlertTriangle className="w-5 h-5" />}
          iconBg="bg-red-500/10"
          iconColor="text-red-400"
          valueClass={totals.overdue_amount_cents > 0 ? 'text-red-400' : 'text-dark-300'}
          compact
        />
        <FinanceKpiCard
          title="Mois avec données"
          value={`${monthsWithData} / 12`}
          icon={<Calendar className="w-5 h-5" />}
          iconBg="bg-green-500/10"
          iconColor="text-green-400"
          compact
        />
      </div>

      {/* Exports */}
      <div className="card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-dark-700">
          <h2 className="text-sm font-semibold text-dark-100">Formats d'export</h2>
        </div>

        {/* CSV */}
        <div className="flex items-center justify-between p-5 border-b border-dark-700/30">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
              <FileText className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <p className="text-sm font-medium">CSV mensuel</p>
              <p className="text-xs text-dark-500">12 lignes · CA + factures par mois</p>
            </div>
          </div>
          <button
            onClick={handleExportCsv}
            disabled={exportCsv.isPending}
            className="btn-primary btn-sm flex items-center gap-2 min-h-[44px]"
          >
            {exportCsv.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            {exportCsv.isPending ? 'Export…' : 'Exporter'}
          </button>
        </div>

        {/* PDF — bientôt */}
        <div className="flex items-center justify-between p-5 opacity-50">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-dark-700 flex items-center justify-center">
              <FileText className="w-5 h-5 text-dark-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-dark-400">PDF rapport</p>
              <p className="text-xs text-dark-500">Rapport complet avec graphiques</p>
            </div>
          </div>
          <span className="text-xs text-dark-500 px-3 py-1 rounded-full border border-dark-600">Bientôt</span>
        </div>
      </div>

      {/* Feedback */}
      {exportError != null && (
        <div className="flex items-center gap-2 text-red-400 text-sm px-4">
          {exportError}
        </div>
      )}
      {exported && (
        <div className="flex items-center gap-2 text-green-400 text-sm px-4">
          <CheckCircle className="w-4 h-4" />
          Fichier téléchargé
        </div>
      )}
    </div>
  )
}
