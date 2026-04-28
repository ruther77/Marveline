import { useParams, useNavigate, useSearch } from '@tanstack/react-router'
import { AlertTriangle, TrendingDown, Package, RotateCcw, BarChart3 } from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import { useLowStockProducts, useProductStock } from '@/api/queries'

type AlertLevel = 'critical' | 'low'

const LEVEL_CONFIG: Record<AlertLevel, {
  label: string
  chip: string
  heroColor: string
  alertStyle: string
  alertIcon: React.ReactNode
  alertText: string
}> = {
  critical: {
    label: 'Stock · Critique',
    chip: 'bg-red-500/15 text-red-400 border-red-500/30',
    heroColor: 'border-orange-500/30 bg-orange-500/5',
    alertStyle: 'border-orange-500/30 bg-orange-500/5',
    alertIcon: <AlertTriangle className="w-5 h-5 text-orange-400 shrink-0 mt-0.5" />,
    alertText: 'Stock insuffisant pour les réservations prévues. Priorité de réassort recommandée.',
  },
  low: {
    label: 'Stock · Faible',
    chip: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
    heroColor: 'border-yellow-500/30 bg-yellow-500/5',
    alertStyle: 'border-blue-500/30 bg-blue-500/5',
    alertIcon: <TrendingDown className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />,
    alertText: 'Le stock est bas mais encore suffisant pour les sorties prévues aujourd\'hui.',
  },
}

export default function StockAlertPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const search = useSearch({ strict: false }) as { level?: string }
  const navigate = useNavigate()

  const productId = parseInt(id, 10)
  const level: AlertLevel = search.level === 'low' ? 'low' : 'critical'
  const cfg = LEVEL_CONFIG[level]

  const { data: stockDetail, isLoading } = useProductStock(productId)
  const { data: lowStockProducts = [] } = useLowStockProducts({ limit: 1000 })
  const lowStockEntry = lowStockProducts.find((p) => p.id === productId)

  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="card p-6 h-28 skel/40 rounded" />
        <div className="card p-4 h-16 skel/40 rounded" />
        <div className="card p-4 grid grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 skel rounded" />
          ))}
        </div>
        <div className="card p-4 h-32 skel/40 rounded" />
      </div>
    )
  }

  const available = stockDetail?.qty_available ?? 0
  const reserved = stockDetail?.qty_reserved ?? 0
  const total = stockDetail?.total ?? 0
  const onLocation = stockDetail?.qty_on_location ?? 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <BackButton />
        <div>
          <h1 className="text-lg font-semibold">{cfg.label}</h1>
          <p className="text-sm text-dark-400">Produit #{productId}</p>
        </div>
      </div>

      {/* Hero */}
      <div className={`card p-6 border ${cfg.heroColor}`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs text-dark-400 uppercase tracking-wide mb-1">
              {stockDetail ? `Produit · ${stockDetail.product_id}` : `#${productId}`}
            </p>
            <div className="flex items-baseline gap-2 mb-1">
              <span className={`text-3xl font-bold ${level === 'critical' ? 'text-red-400' : 'text-yellow-400'}`}>
                {available}
              </span>
              <span className="text-dark-400 text-sm">dispo</span>
            </div>
            <p className="text-sm text-dark-400">
              {level === 'critical'
                ? 'Seuil minimum dépassé · Alerte critique'
                : 'Seuil d\'alerte atteint · Niveau faible'}
            </p>
            {lowStockEntry && (
              <p className="text-xs text-dark-500 mt-2">
                Endpoint `/products/low-stock`: {lowStockEntry.available_quantity} disponible(s) sur {lowStockEntry.stock_quantity}.
              </p>
            )}
          </div>
          <span className={`px-2.5 py-1 text-xs font-medium rounded-full border shrink-0 ${cfg.chip}`}>
            {level === 'critical' ? 'Critique' : 'Faible'}
          </span>
        </div>
      </div>

      {/* Alerte */}
      <div className={`card p-4 border ${cfg.alertStyle}`}>
        <div className="flex gap-4 items-start">
          {cfg.alertIcon}
          <p className="text-sm text-dark-300">{cfg.alertText}</p>
        </div>
      </div>

      {/* Grille 4 stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div className="card p-4 text-center">
          <p className="text-lg font-bold">{total}</p>
          <p className="text-xs text-dark-400 mt-0.5">Total</p>
        </div>
        <div className="card p-4 text-center">
          <p className={`text-lg font-bold ${level === 'critical' ? 'text-red-400' : 'text-yellow-400'}`}>
            {available}
          </p>
          <p className="text-xs text-dark-400 mt-0.5">Disponible</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-lg font-bold text-orange-400">{reserved}</p>
          <p className="text-xs text-dark-400 mt-0.5">Réservé</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-lg font-bold text-blue-400">{onLocation}</p>
          <p className="text-xs text-dark-400 mt-0.5">En location</p>
        </div>
      </div>

      {/* Section selon level */}
      {level === 'critical' ? (
        <div className="card p-4 space-y-4">
          <p className="text-xs uppercase tracking-wide text-dark-400">Cycle de traitement</p>
          <div className="space-y-4">
            {/* Étape 1 — active */}
            <div className="flex items-start gap-4">
              <div className="w-7 h-7 rounded-full bg-orange-500/20 border-2 border-orange-500 flex items-center justify-center shrink-0 mt-0.5">
                <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />
              </div>
              <div>
                <p className="text-sm font-medium">Alerte critique</p>
                <p className="text-xs text-dark-400">Seuil minimum dépassé</p>
              </div>
            </div>
            <div className="ml-4.5 w-px h-4 bg-dark-600" />
            {/* Étape 2 */}
            <div className="flex items-start gap-4">
              <div className="w-7 h-7 rounded-full bg-dark-800 border border-dark-600 flex items-center justify-center shrink-0 mt-0.5">
                <Package className="w-3.5 h-3.5 text-dark-500" />
              </div>
              <div>
                <p className="text-sm text-dark-400">Réassort en cours</p>
                <p className="text-xs text-dark-500">Commande fournisseur envoyée</p>
              </div>
            </div>
            <div className="ml-4.5 w-px h-4 bg-dark-600" />
            {/* Étape 3 */}
            <div className="flex items-start gap-4">
              <div className="w-7 h-7 rounded-full bg-dark-800 border border-dark-600 flex items-center justify-center shrink-0 mt-0.5">
                <span className="text-xs">✅</span>
              </div>
              <div>
                <p className="text-sm text-dark-400">Rupture résolue</p>
                <p className="text-xs text-dark-500">Niveau stock stabilisé</p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="card p-4 space-y-4">
          <p className="text-xs uppercase tracking-wide text-dark-400">Actions recommandées</p>
          <div className="space-y-2">
            <div className="flex items-center gap-4 p-4 rounded-lg bg-dark-900">
              <span className="text-lg shrink-0">🚛</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">Créer réassort préventif</p>
                <p className="text-xs text-dark-400">Planifier un approvisionnement</p>
              </div>
              <span className="px-2 py-0.5 text-xs rounded-full border bg-blue-500/15 text-blue-400 border-blue-500/30 shrink-0">
                Planifier
              </span>
            </div>
            <div className="flex items-center gap-4 p-4 rounded-lg bg-dark-900">
              <span className="text-lg shrink-0">⚠️</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">Surveiller les réservations</p>
                <p className="text-xs text-dark-400">Vérifier les conflits de stock</p>
              </div>
              <span className="px-2 py-0.5 text-xs rounded-full border bg-orange-500/15 text-orange-400 border-orange-500/30 shrink-0">
                Priorité
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Actions principales */}
      <div className="space-y-2">
        <div className="flex gap-2">
          <button
            onClick={() => navigate({ to: '/stock/reorder' })}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-4.5 bg-primary-500/10 text-primary-400 border border-primary-500/30 rounded-xl font-medium text-sm hover:bg-primary-500/20"
          >
            + Lancer réassort
          </button>
          <button
            onClick={() => navigate({ to: '/stock/adjustments' })}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-4.5 border border-dark-600 text-dark-300 rounded-xl font-medium text-sm hover:bg-dark-600"
          >
            ✏️ Ajuster stock
          </button>
        </div>

        <button
          onClick={() => navigate({ to: '/stock/items/$id', params: { id } })}
          className="w-full flex items-center justify-center gap-2 px-4 py-4 border border-dark-600 text-dark-400 rounded-xl text-sm hover:bg-dark-600"
        >
          <BarChart3 className="w-4 h-4" />
          Voir états endommagé / réparation
        </button>
        <button
          onClick={() => navigate({ to: '/operations' })}
          className="w-full flex items-center justify-center gap-2 px-4 py-4 border border-dark-600 text-dark-400 rounded-xl text-sm hover:bg-dark-600"
        >
          <RotateCcw className="w-4 h-4" />
          Voir les opérations
        </button>
        <button
          onClick={() => navigate({ to: '/stock/items' })}
          className="w-full flex items-center justify-center gap-2 px-4 py-4 border border-dark-600 text-dark-400 rounded-xl text-sm hover:bg-dark-600"
        >
          <Package className="w-4 h-4" />
          Suivre le réassort
        </button>
      </div>
    </div>
  )
}
