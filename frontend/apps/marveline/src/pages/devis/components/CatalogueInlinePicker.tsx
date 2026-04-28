import { useState, useEffect } from 'react'
import { Search, Check, Layers, Package } from 'lucide-react'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { useProductsList, useCategoriesList, useBundlesList } from '@/api/queries'
import { formatCents } from '@/lib/utils'
import type { Product, Bundle } from '@/types/product'

export interface CataloguePickerLine {
  product_id?: number
  bundle_id?: number
  product_name: string
  quantity: number
  unit_price_cents: number
  image_url?: string | null
  short_description?: string | null
}

interface Props {
  onSelect: (line: CataloguePickerLine) => void
}

type PickerTab = 'products' | 'bundles'

export function CatalogueInlinePicker({ onSelect }: Props) {
  const [tab, setTab] = useState<PickerTab>('products')
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [added, setAdded] = useState<number | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  const { data: productsData, isLoading, error, refetch } = useProductsList({
    search: debouncedSearch || undefined,
    category: categoryFilter || undefined,
    available_only: true,
    limit: 30,
  })

  const { data: categories } = useCategoriesList(true)

  const {
    data: bundlesData,
    isLoading: bundlesLoading,
    error: bundlesError,
    refetch: refetchBundles,
  } = useBundlesList({ limit: 50, active_only: true }, tab === 'bundles')

  const products = productsData?.items ?? []
  const allBundles: Bundle[] = bundlesData?.items ?? []
  const bundles = debouncedSearch
    ? allBundles.filter((b) => b.name.toLowerCase().includes(debouncedSearch.toLowerCase()))
    : allBundles

  function handleAdd(product: Product) {
    onSelect({
      product_id: product.id,
      product_name: product.name,
      quantity: 1,
      unit_price_cents: product.price_per_day_cents ?? 0,
      image_url: product.image_url ?? null,
    })
    setAdded(product.id)
    setTimeout(() => setAdded(null), 800)
  }

  function handleAddBundle(bundle: Bundle) {
    onSelect({
      bundle_id: bundle.id,
      product_name: bundle.name,
      quantity: 1,
      unit_price_cents: bundle.bundle_price_cents ?? 0,
      image_url: bundle.image_url ?? null,
      short_description: bundle.short_description ?? null,
    })
    setAdded(bundle.id)
    setTimeout(() => setAdded(null), 800)
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-dark-300">Catalogue</h3>

      {/* Onglets */}
      <div className="flex gap-1 bg-dark-900/50 rounded-lg p-1">
        <button
          type="button"
          onClick={() => setTab('products')}
          className={`flex-1 py-1.5 px-3 rounded-md text-xs font-medium transition-colors ${tab === 'products' ? 'bg-dark-600 text-dark-50' : 'text-dark-400 hover:text-dark-200'}`}
        >
          Produits
        </button>
        <button
          type="button"
          onClick={() => setTab('bundles')}
          className={`flex-1 py-1.5 px-3 rounded-md text-xs font-medium transition-colors flex items-center justify-center gap-1 ${tab === 'bundles' ? 'bg-dark-600 text-dark-50' : 'text-dark-400 hover:text-dark-200'}`}
        >
          <Layers className="w-3 h-3" /> Packs
        </button>
      </div>

      {/* Recherche */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-dark-500" />
          <input
            type="text"
            placeholder="Rechercher..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-8 w-full text-sm py-1.5"
          />
        </div>
        {tab === 'products' && (
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="input text-xs py-1.5 w-32"
          >
            <option value="">Toutes</option>
            {categories?.filter((c) => c.parent_id != null).map((cat) => (
              <option key={cat.id} value={cat.slug}>{cat.name}</option>
            ))}
          </select>
        )}
      </div>

      {/* Liste */}
      <div className="space-y-1 max-h-[60vh] overflow-y-auto">
        {tab === 'products' && (
          <>
            {isLoading && (
              <div className="space-y-2 animate-pulse">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-12 skel/50 rounded-lg" />
                ))}
              </div>
            )}
            {!isLoading && error && <ErrorState onRetry={() => refetch()} />}
            {!isLoading && !error && products.length === 0 && (
              <p className="text-center text-dark-500 py-4 text-xs">Aucun produit</p>
            )}
            {products.map((product) => {
              const isAdded = added === product.id
              return (
                <button
                  key={product.id}
                  type="button"
                  onClick={() => handleAdd(product)}
                  className="w-full flex items-center gap-3 p-2.5 rounded-lg hover:bg-dark-700/30 border border-transparent hover:border-gold-500/30 transition-colors text-left"
                >
                  {product.image_url ? (
                    <img src={product.image_url} alt="" loading="lazy" className="w-8 h-8 rounded object-cover shrink-0" />
                  ) : (
                    <div className="w-8 h-8 rounded bg-dark-800 flex items-center justify-center shrink-0">
                      <Package className="w-3.5 h-3.5 text-dark-500" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate">{product.name}</p>
                    <p className="text-[10px] text-dark-500">{product.category}</p>
                  </div>
                  <span className="text-xs font-medium shrink-0">{formatCents(product.price_per_day_cents ?? 0)}/j</span>
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 transition-colors ${isAdded ? 'bg-green-500' : 'bg-dark-700 hover:bg-gold-500'}`}>
                    {isAdded ? <Check className="w-3 h-3 text-white" /> : <span className="text-white text-xs">+</span>}
                  </div>
                </button>
              )
            })}
          </>
        )}

        {tab === 'bundles' && (
          <>
            {bundlesLoading && (
              <div className="space-y-2 animate-pulse">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-12 skel/50 rounded-lg" />
                ))}
              </div>
            )}
            {!bundlesLoading && bundlesError && <ErrorState onRetry={() => refetchBundles()} />}
            {!bundlesLoading && !bundlesError && bundles.length === 0 && (
              <p className="text-center text-dark-500 py-4 text-xs">Aucun pack</p>
            )}
            {bundles.map((bundle) => {
              const isAdded = added === bundle.id
              return (
                <button
                  key={bundle.id}
                  type="button"
                  onClick={() => handleAddBundle(bundle)}
                  className="w-full flex items-start gap-3 p-2.5 rounded-lg hover:bg-dark-700/30 border border-transparent hover:border-primary-500/30 transition-colors text-left"
                >
                  <div className="w-10 h-10 rounded-lg overflow-hidden bg-primary-500/10 flex items-center justify-center shrink-0">
                    {bundle.image_url ? (
                      <img src={bundle.image_url} alt={bundle.name} loading="lazy" className="w-full h-full object-cover" />
                    ) : (
                      <Layers className="w-4 h-4 text-primary-400" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <p className="text-xs font-medium truncate">{bundle.name}</p>
                      <span className="text-[9px] px-1 py-0.5 rounded-full bg-primary-500/15 text-primary-400 border border-primary-500/30 shrink-0">Pack</span>
                    </div>
                    {bundle.short_description && (
                      <p className="text-[10px] text-dark-500 truncate mt-0.5">{bundle.short_description}</p>
                    )}
                    <p className="text-[10px] text-dark-400 mt-0.5">{formatCents(bundle.bundle_price_cents ?? 0)}</p>
                  </div>
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-1 transition-colors ${isAdded ? 'bg-green-500' : 'bg-dark-700 hover:bg-primary-500'}`}>
                    {isAdded ? <Check className="w-3 h-3 text-white" /> : <span className="text-white text-xs">+</span>}
                  </div>
                </button>
              )
            })}
          </>
        )}
      </div>
    </div>
  )
}
