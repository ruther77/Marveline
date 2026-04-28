import { useState } from 'react'
import { useProductsList, useDeliveryZonesList } from '@/api/queries'
import { getStockStatus } from '@/types/product'
import { MapPin, Package, Search, CheckCircle, AlertCircle, XCircle } from 'lucide-react'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { cn, formatCents } from '@/lib/utils'

const STOCK_STATUS_LABEL: Record<string, string> = {
  in_stock: 'En stock',
  low_stock: 'Stock faible',
  out_of_stock: 'Rupture',
}

const STOCK_STATUS_COLOR: Record<string, string> = {
  in_stock: 'text-green-400',
  low_stock: 'text-yellow-400',
  out_of_stock: 'text-red-400',
}

const STOCK_STATUS_ICON = {
  in_stock: CheckCircle,
  low_stock: AlertCircle,
  out_of_stock: XCircle,
}

export default function CatalogueAvailabilityPage() {
  const [selectedZone, setSelectedZone] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [stockFilter, setStockFilter] = useState<'all' | 'in_stock' | 'low_stock' | 'out_of_stock'>('all')

  const { data: productsData, isLoading: loadingProducts, error: errorProducts, refetch: refetchProducts } = useProductsList({
    limit: 1000,
    active_only: true,
  })
  const { data: zones = [], isLoading: loadingZones } = useDeliveryZonesList()

  const products = productsData?.items || []
  const activeZones = zones.filter((z) => z.is_active)
  const selectedZoneData = activeZones.find((z) => z.id === selectedZone)

  const filtered = products.filter((p) => {
    const matchSearch =
      !search ||
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.sku.toLowerCase().includes(search.toLowerCase())
    const status = getStockStatus(p)
    const matchStock = stockFilter === 'all' || status === stockFilter
    return matchSearch && matchStock
  })

  const isLoading = loadingProducts || loadingZones

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2 min-w-0">
          <MapPin className="w-6 h-6 text-primary-400" />
          Disponibilité catalogue
        </h1>
        <p className="text-dark-400 mt-1">
          Consultez la disponibilité des produits par zone de livraison
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Panneau gauche — zones */}
        <div className="md:col-span-1 space-y-4">
          <h2 className="text-sm font-medium text-dark-300 uppercase tracking-wide">
            Zones de livraison
          </h2>
          {loadingZones ? (
            <div className="space-y-2 animate-pulse">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-8 skel rounded-lg" />
              ))}
            </div>
          ) : activeZones.length === 0 ? (
            <p className="text-dark-400 text-sm">Aucune zone configurée</p>
          ) : (
            <div className="space-y-1">
              <button
                onClick={() => setSelectedZone(null)}
                className={cn(
                  'w-full text-left px-4 py-2 rounded-lg text-sm transition-colors',
                  selectedZone === null
                    ? 'bg-primary-600 text-white'
                    : 'hover:bg-dark-900 text-dark-300'
                )}
              >
                Toutes les zones
              </button>
              {activeZones.map((zone) => (
                <button
                  key={zone.id}
                  onClick={() => setSelectedZone(zone.id === selectedZone ? null : zone.id)}
                  className={cn(
                    'w-full text-left px-4 py-2 rounded-lg text-sm transition-colors',
                    zone.id === selectedZone
                      ? 'bg-primary-600 text-white'
                      : 'hover:bg-dark-900 text-dark-300'
                  )}
                >
                  <span className="font-mono font-medium">{zone.department_code}</span>
                  <span className="ml-2">{zone.department_name}</span>
                </button>
              ))}
            </div>
          )}

          {/* Info zone sélectionnée */}
          {selectedZoneData && (
            <div className="card p-4 space-y-1.5 text-sm mt-4">
              <p className="text-dark-400 text-xs uppercase tracking-wide">Zone sélectionnée</p>
              <p className="font-medium">{selectedZoneData.department_name}</p>
              <p className="text-dark-400">
                Livraison : <span className="">{formatCents(selectedZoneData.delivery_fee_cents)}</span>
              </p>
              {selectedZoneData.sunday_surcharge_cents > 0 && (
                <p className="text-dark-400">
                  Supplément dimanche :{' '}
                  <span className="text-yellow-400">{formatCents(selectedZoneData.sunday_surcharge_cents)}</span>
                </p>
              )}
              {selectedZoneData.notes && (
                <p className="text-dark-500 text-xs">{selectedZoneData.notes}</p>
              )}
            </div>
          )}
        </div>

        {/* Panneau droit — produits */}
        <div className="md:col-span-3 space-y-4">
          {/* Filtres */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
              <input
                type="text"
                placeholder="Rechercher un produit…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input pl-9 text-sm"
              />
            </div>
            <select
              value={stockFilter}
              onChange={(e) => setStockFilter(e.target.value as typeof stockFilter)}
              className="input text-sm w-auto"
            >
              <option value="all">Tous les stocks</option>
              <option value="in_stock">En stock</option>
              <option value="low_stock">Stock faible</option>
              <option value="out_of_stock">Rupture</option>
            </select>
          </div>

          <p className="text-xs text-dark-500">
            {filtered.length} produit{filtered.length !== 1 ? 's' : ''}
            {selectedZone ? ` · Zone ${selectedZoneData?.department_code ?? ''} sélectionnée` : ''}
          </p>

          {errorProducts ? (
            <ErrorState onRetry={() => refetchProducts()} />
          ) : isLoading ? (
            <div className="space-y-2 animate-pulse">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="card p-4 space-y-2">
                  <div className="h-3 skel rounded w-40" />
                  <div className="h-2 skel rounded w-28" />
                </div>
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-10 border border-dashed border-dark-600 rounded-xl">
              <Package className="w-10 h-10 text-dark-600 mx-auto mb-2" />
              <p className="text-dark-400">Aucun produit trouvé</p>
            </div>
          ) : (
            <div className="divide-y divide-dark-600 border border-dark-600 rounded-xl overflow-hidden">
              {filtered.map((product) => {
                const status = getStockStatus(product)
                const Icon = STOCK_STATUS_ICON[status] || Package
                return (
                  <div key={product.id} className="flex items-center gap-4 px-4 py-4 hover:bg-dark-900/40">
                    <Icon className={cn('w-5 h-5 flex-shrink-0', STOCK_STATUS_COLOR[status])} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{product.name}</p>
                      <p className="text-xs text-dark-500 font-mono">{product.sku}</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className={cn('text-sm font-medium', STOCK_STATUS_COLOR[status])}>
                        {STOCK_STATUS_LABEL[status]}
                      </p>
                      <p className="text-xs text-dark-500">
                        {product.available_quantity} / {product.stock_quantity} dispo
                      </p>
                    </div>
                    {selectedZoneData && (
                      <div className="text-right flex-shrink-0 pl-4 border-l border-dark-600 w-24">
                        <p className="text-xs text-dark-400">Livraison</p>
                        <p className="text-sm font-medium">
                          {formatCents(selectedZoneData.delivery_fee_cents)}
                        </p>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
