import { PageHeader } from '@/components/PageHeader'
import { useStockCoverage } from '@/api/queries'
import { BarChart2, TrendingDown, AlertTriangle, CheckCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StockCoverageStatus } from '@/types/stock_management'

const STATUS_CONFIG: Record<StockCoverageStatus, { label: string; color: string; icon: React.ReactNode }> = {
  critical: {
    label: 'Critique',
    color: 'bg-red-500/10 text-red-400',
    icon: <AlertTriangle className="w-3 h-3" />,
  },
  low: {
    label: 'Faible',
    color: 'bg-yellow-500/10 text-yellow-400',
    icon: <TrendingDown className="w-3 h-3" />,
  },
  ok: {
    label: 'Correct',
    color: 'bg-blue-500/10 text-blue-400',
    icon: <BarChart2 className="w-3 h-3" />,
  },
  good: {
    label: 'Bon',
    color: 'bg-green-500/10 text-green-400',
    icon: <CheckCircle className="w-3 h-3" />,
  },
}

export default function StockCoveragePage() {
  const { data, isLoading } = useStockCoverage()

  const items = data?.items ?? []
  const critical = items.filter((i) => i.status === 'critical').length
  const low = items.filter((i) => i.status === 'low').length

  return (
    <div className="space-y-6">
      <PageHeader title="Couverture stock" subtitle="Analyse de la rotation et de la couverture sur 30 jours" />

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm text-dark-400">Produits analysés</p>
              <p className="text-2xl font-bold mt-1">{items.length}</p>
            </div>
            <BarChart2 className="w-8 h-8 text-dark-400" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm text-dark-400">Couverture critique (&lt; 7j)</p>
              <p className="text-2xl font-bold text-red-500 mt-1">{critical}</p>
            </div>
            <AlertTriangle className="w-8 h-8 text-red-500" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm text-dark-400">Couverture faible (7-30j)</p>
              <p className="text-2xl font-bold text-yellow-500 mt-1">{low}</p>
            </div>
            <TrendingDown className="w-8 h-8 text-yellow-500" />
          </div>
        </div>
      </div>

      {/* Tableau */}
      <div className="card p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-600">
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">Produit</th>
                <th className="text-right py-4 px-4 text-sm font-medium text-dark-400">Dispo / Total</th>
                <th className="text-right py-4 px-4 text-sm font-medium text-dark-400">Mouvements 30j</th>
                <th className="text-right py-4 px-4 text-sm font-medium text-dark-400">Moy/jour</th>
                <th className="text-right py-4 px-4 text-sm font-medium text-dark-400">Couverture</th>
                <th className="text-right py-4 px-4 text-sm font-medium text-dark-400">Rotation</th>
                <th className="text-center py-4 px-4 text-sm font-medium text-dark-400">Statut</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 7 }).map((_, i) => (
                  <tr key={i} className="border-b border-dark-600 animate-pulse">
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-36" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-10" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-10" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-14" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-16" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-16" /></td>
                    <td className="py-4 px-4"><div className="h-5 bg-dark-900 rounded w-20" /></td>
                  </tr>
                ))
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-dark-400">
                    Aucun produit
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const cfg = STATUS_CONFIG[item.status]
                  return (
                    <tr key={item.product_id} className="border-b border-dark-600 hover:bg-dark-900/50">
                      <td className="py-4 px-4">
                        <div className="font-medium">{item.product_name}</div>
                        <div className="text-xs text-dark-500 font-mono">{item.sku}</div>
                      </td>
                      <td className="py-4 px-4 text-right text-sm">
                        <span className="text-green-400">{item.available_qty}</span>
                        <span className="text-dark-500"> / {item.total_qty}</span>
                      </td>
                      <td className="py-4 px-4 text-right text-sm text-dark-300">
                        {item.movements_30d}
                      </td>
                      <td className="py-4 px-4 text-right text-sm text-dark-300">
                        {item.avg_daily_movements.toFixed(2)}
                      </td>
                      <td className="py-4 px-4 text-right">
                        {item.days_of_coverage === null ? (
                          <span className="text-sm text-dark-500">∞</span>
                        ) : (
                          <span
                            className={cn(
                              'text-sm font-medium',
                              item.days_of_coverage < 7
                                ? 'text-red-400'
                                : item.days_of_coverage < 30
                                ? 'text-yellow-400'
                                : 'text-green-400'
                            )}
                          >
                            {item.days_of_coverage}j
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-4 text-right text-sm text-dark-300">
                        {item.rotation_rate.toFixed(1)}%
                      </td>
                      <td className="py-4 px-4 text-center">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
                            cfg.color
                          )}
                        >
                          {cfg.icon}
                          {cfg.label}
                        </span>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
        {data && (
          <div className="px-4 py-2 border-t border-dark-600 text-xs text-dark-500">
            Calculé le{' '}
            {new Date(data.computed_at).toLocaleString('fr-FR', {
              dateStyle: 'short',
              timeStyle: 'short',
            })}
          </div>
        )}
      </div>
    </div>
  )
}
