import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { productsApi } from '@/api/products'
import { Search, Package, AlertCircle, CheckCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getStockStatus } from '@/types/product'

export default function InventoryPage() {
  const [search, setSearch] = useState('')

  // Requête pour l'affichage paginé
  const { data, isLoading } = useQuery({
    queryKey: ['products-inventory', search],
    queryFn: () =>
      productsApi.getProducts({
        page: 1,
        page_size: 100,
        active_only: true,
      }),
  })

  const products = data?.items || []

  // Calculer statistiques côté frontend (backend n'a pas d'endpoint statistics)
  const inStock = products.filter((p) => getStockStatus(p) === 'in_stock').length
  const lowStock = products.filter((p) => getStockStatus(p) === 'low_stock').length
  const outStock = products.filter((p) => getStockStatus(p) === 'out_of_stock').length

  const getStockLevel = (product: { available_quantity: number; stock_quantity: number }) => {
    if (product.stock_quantity === 0) return 0
    return Math.round((product.available_quantity / product.stock_quantity) * 100)
  }

  const getStockColor = (status: string) => {
    switch (status) {
      case 'in_stock':
        return 'text-green-500'
      case 'low_stock':
        return 'text-yellow-500'
      case 'out_of_stock':
        return 'text-red-500'
      default:
        return 'text-dark-400'
    }
  }

  const getStockIcon = (status: string) => {
    switch (status) {
      case 'in_stock':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'low_stock':
        return <AlertCircle className="w-5 h-5 text-yellow-500" />
      case 'out_of_stock':
        return <AlertCircle className="w-5 h-5 text-red-500" />
      default:
        return <Package className="w-5 h-5 text-dark-400" />
    }
  }

  // Filtrer par recherche côté client
  const filteredProducts = search
    ? products.filter(
        (p) =>
          p.name.toLowerCase().includes(search.toLowerCase()) ||
          p.sku.toLowerCase().includes(search.toLowerCase())
      )
    : products

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Inventaire & Stock</h1>
        <p className="text-dark-400 mt-1">Vue d'ensemble du stock disponible</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-dark-400">En stock</p>
              <p className="text-2xl font-bold text-green-500 mt-1">{inStock}</p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-dark-400">Stock faible</p>
              <p className="text-2xl font-bold text-yellow-500 mt-1">{lowStock}</p>
            </div>
            <AlertCircle className="w-8 h-8 text-yellow-500" />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-dark-400">Rupture</p>
              <p className="text-2xl font-bold text-red-500 mt-1">{outStock}</p>
            </div>
            <AlertCircle className="w-8 h-8 text-red-500" />
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="card">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
          <input
            type="text"
            placeholder="Rechercher un produit..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
          />
        </div>
      </div>

      {/* Products Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading ? (
          <div className="col-span-full text-center py-8 text-dark-400">
            Chargement...
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="col-span-full text-center py-8 text-dark-400">
            Aucun produit trouvé
          </div>
        ) : (
          filteredProducts.map((product) => {
            const stockStatus = getStockStatus(product)
            return (
              <div key={product.id} className="card">
                <div className="flex items-start gap-4">
                  <div className="p-3 bg-dark-800 rounded-lg">
                    {getStockIcon(stockStatus)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium truncate">{product.name}</h3>
                    <p className="text-sm text-dark-400 font-mono">{product.sku}</p>

                    <div className="mt-3 space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-dark-400">Stock</span>
                        <span
                          className={cn('font-medium', getStockColor(stockStatus))}
                        >
                          {product.available_quantity} / {product.stock_quantity}
                        </span>
                      </div>

                      <div className="w-full bg-dark-700 rounded-full h-2">
                        <div
                          className={cn(
                            'h-2 rounded-full transition-all',
                            stockStatus === 'in_stock' && 'bg-green-500',
                            stockStatus === 'low_stock' && 'bg-yellow-500',
                            stockStatus === 'out_of_stock' && 'bg-red-500'
                          )}
                          style={{
                            width: `${Math.min(getStockLevel(product), 100)}%`,
                          }}
                        />
                      </div>

                      <div className="flex items-center justify-between text-sm">
                        <span className="text-dark-400">Prix/jour</span>
                        <span className="font-medium">{product.price_per_day_euros.toFixed(2)} €</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
