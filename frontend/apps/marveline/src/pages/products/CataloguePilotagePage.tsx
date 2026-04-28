import { useProductsList, useAnalyticsKpis } from '@/api/queries'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { getStockStatus } from '@/types/product'
import { formatCents } from '@/lib/utils'
import {
  Package,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  BarChart2,
  Tag,
  Euro,
  Archive,
  ShoppingCart,
} from 'lucide-react'

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
      <div>
        <p className="text-sm text-dark-400">{label}</p>
        <p className={`text-2xl font-bold mt-0.5 ${color}`}>{value}</p>
        {sub && <p className="text-xs text-dark-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

export default function CataloguePilotagePage() {
  const { data: productsData, isLoading, error, refetch } = useProductsList({ limit: 500 })
  const { data: analytics } = useAnalyticsKpis(365)

  const products = productsData?.items || []

  // KPIs catalogue
  const totalProducts = products.length
  const activeProducts = products.filter((p) => p.is_active).length
  const inactiveProducts = totalProducts - activeProducts

  const totalStock = products.reduce((s, p) => s + p.stock_quantity, 0)
  const totalAvailable = products.reduce((s, p) => s + p.available_quantity, 0)
  const utilizationRate =
    totalStock > 0 ? Math.round(((totalStock - totalAvailable) / totalStock) * 100) : 0

  const lowStock = products.filter((p) => getStockStatus(p) === 'low_stock').length
  const outOfStock = products.filter((p) => getStockStatus(p) === 'out_of_stock').length
  const inStock = products.filter((p) => getStockStatus(p) === 'in_stock').length

  // Valeur du parc (prix/jour × stock — indicateur proxy)
  const totalValuePerDay = products.reduce(
    (s, p) => s + p.price_per_day_euros * p.stock_quantity,
    0
  )

  // Répartition par catégorie (champ string sur Product)
  const catMap: Record<string, { count: number; available: number; total: number }> = {}
  for (const p of products) {
    const key = p.category || '(Sans catégorie)'
    if (!catMap[key]) catMap[key] = { count: 0, available: 0, total: 0 }
    catMap[key].count++
    catMap[key].available += p.available_quantity
    catMap[key].total += p.stock_quantity
  }
  const byCat = Object.entries(catMap)
    .map(([name, v]) => ({ name, ...v }))
    .sort((a, b) => b.count - a.count)

  const uncategorized = products.filter((p) => !p.category).length

  if (error) {
    return <ErrorState onRetry={() => refetch()} />
  }

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 skel rounded w-48" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="card p-4 space-y-2">
              <div className="h-3 skel rounded w-28" />
              <div className="h-7 skel rounded w-12" />
            </div>
          ))}
        </div>
        <div className="card divide-y divide-dark-600">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-4">
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-36" />
                <div className="h-2 skel rounded w-52" />
              </div>
              <div className="h-3 skel rounded w-10 shrink-0" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2 min-w-0">
          <BarChart2 className="w-6 h-6 text-primary-400" />
          Pilotage catalogue
        </h1>
        <p className="text-dark-400 mt-1">Indicateurs clés de votre catalogue et de votre parc</p>
      </div>

      {/* KPIs ligne 1 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Articles actifs"
          value={activeProducts}
          sub={`${inactiveProducts} inactif${inactiveProducts !== 1 ? 's' : ''}`}
          icon={CheckCircle}
          color="text-green-400"
        />
        <KpiCard
          label="Catégories utilisées"
          value={byCat.length}
          sub={uncategorized > 0 ? `${uncategorized} sans catégorie` : 'Tous catégorisés'}
          icon={Tag}
          color="text-blue-400"
        />
        <KpiCard
          label="Taux d'utilisation"
          value={`${analytics?.utilization_rate ?? utilizationRate} %`}
          sub={`${analytics?.total_rented ?? (totalStock - totalAvailable)} / ${analytics?.total_stock ?? totalStock} unites`}
          icon={TrendingUp}
          color={(analytics?.utilization_rate ?? utilizationRate) > 80 ? 'text-orange-400' : 'text-primary-400'}
        />
        <KpiCard
          label="Panier moyen"
          value={analytics ? formatCents(analytics.avg_basket_cents) : '—'}
          sub={analytics ? `${analytics.total_reservations} reservation${analytics.total_reservations > 1 ? 's' : ''} (12 mois)` : ''}
          icon={ShoppingCart}
          color="text-gold-400"
        />
      </div>

      {/* KPIs ligne 2 — état stock */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div className="card p-4 text-center">
          <CheckCircle className="w-8 h-8 text-green-500 mx-auto mb-2" />
          <p className="text-2xl font-bold text-green-400">{inStock}</p>
          <p className="text-sm text-dark-400">En stock</p>
        </div>
        <div className="card p-4 text-center">
          <AlertCircle className="w-8 h-8 text-yellow-500 mx-auto mb-2" />
          <p className="text-2xl font-bold text-yellow-400">{lowStock}</p>
          <p className="text-sm text-dark-400">Stock faible</p>
        </div>
        <div className="card p-4 text-center">
          <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
          <p className="text-2xl font-bold text-red-400">{outOfStock}</p>
          <p className="text-sm text-dark-400">Rupture</p>
        </div>
      </div>

      {/* Répartition par catégorie */}
      <div className="card">
        <div className="p-4 border-b border-dark-600 flex items-center gap-2">
          <Package className="w-4 h-4 text-dark-400" />
          <h2 className="font-medium">Répartition par catégorie</h2>
        </div>
        {byCat.length === 0 ? (
          <div className="p-8 text-center text-dark-400 flex flex-col items-center gap-2">
            <Archive className="w-10 h-10 text-dark-600" />
            <p>Aucun produit catégorisé</p>
          </div>
        ) : (
          <div className="divide-y divide-dark-600">
            {byCat.map((cat: { name: string; count: number; available: number; total: number }) => {
              const catUtilRate =
                cat.total > 0
                  ? Math.round(((cat.total - cat.available) / cat.total) * 100)
                  : 0
              const barWidth = totalProducts > 0 ? (cat.count / totalProducts) * 100 : 0
              return (
                <div key={cat.name} className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">{cat.name}</span>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="text-dark-400">{cat.count} article{cat.count !== 1 ? 's' : ''}</span>
                      <span className="text-dark-500">{cat.available} dispo / {cat.total}</span>
                      <span
                        className={
                          catUtilRate > 80
                            ? 'text-orange-400'
                            : catUtilRate > 50
                            ? 'text-yellow-400'
                            : 'text-green-400'
                        }
                      >
                        {catUtilRate} %
                      </span>
                    </div>
                  </div>
                  <div className="h-1.5 bg-dark-900 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary-500 rounded-full"
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Top 10 produits les plus loues */}
      <div className="card">
        <div className="p-4 border-b border-dark-600 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-dark-400" />
          <h2 className="font-medium">Top 10 produits les plus loues</h2>
        </div>
        {analytics?.top_products?.length ? (
          <div className="divide-y divide-dark-600">
            {analytics.top_products.map((tp, idx) => {
              const maxCount = analytics.top_products[0]?.rental_count ?? 1
              const barWidth = maxCount > 0 ? (tp.rental_count / maxCount) * 100 : 0
              return (
                <div key={tp.product_id} className="p-4 flex items-center gap-4">
                  <span className="w-6 text-center text-sm font-bold text-dark-400">{idx + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{tp.product_name}</p>
                    <div className="flex items-center gap-3 mt-0.5">
                      {tp.category && <span className="text-xs text-dark-500">{tp.category}</span>}
                      <span className="text-xs text-dark-400">{tp.rental_count} location{tp.rental_count > 1 ? 's' : ''}</span>
                    </div>
                    <div className="h-1 bg-dark-900 rounded-full mt-1.5 overflow-hidden">
                      <div className="h-full bg-primary-500 rounded-full" style={{ width: `${barWidth}%` }} />
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-bold text-gold-400">{formatCents(tp.revenue_cents)}</p>
                    <p className="text-xs text-dark-500">{tp.total_quantity} unites</p>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="p-8 text-center text-dark-400 flex flex-col items-center gap-2">
            <Archive className="w-10 h-10 text-dark-600" />
            <p>Aucune donnee de location</p>
          </div>
        )}
      </div>
    </div>
  )
}
