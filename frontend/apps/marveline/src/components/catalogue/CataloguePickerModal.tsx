import { useState, useEffect } from 'react'
import { Search, Check, Layers, Package } from 'lucide-react'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { Modal } from '@shared/components/ui/Modal'
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

interface CataloguePickerModalProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (line: CataloguePickerLine) => void
}

type PickerTab = 'products' | 'bundles'

export function CataloguePickerModal({ isOpen, onClose, onSelect }: CataloguePickerModalProps) {
  const [tab, setTab] = useState<PickerTab>('products')
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [added, setAdded] = useState<number | null>(null)
  const [pendingSelections, setPendingSelections] = useState<CataloguePickerLine[]>([])

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  const { data: productsData, isLoading, error, refetch } = useProductsList(
    {
      search: debouncedSearch || undefined,
      category: categoryFilter || undefined,
      available_only: true,
      limit: 30,
    },
    isOpen
  )

  const { data: categories } = useCategoriesList(true, isOpen)

  const {
    data: bundlesData,
    isLoading: bundlesLoading,
    error: bundlesError,
    refetch: refetchBundles,
  } = useBundlesList({ limit: 50, active_only: true }, isOpen && tab === 'bundles')

  const products = productsData?.items ?? []
  const allBundles: Bundle[] = bundlesData?.items ?? []
  const bundles = debouncedSearch
    ? allBundles.filter((b) => b.name.toLowerCase().includes(debouncedSearch.toLowerCase()))
    : allBundles

  function handleAddBundle(bundle: Bundle) {
    setPendingSelections((prev) => [
      ...prev,
      {
        bundle_id: bundle.id,
        product_name: bundle.name,
        quantity: 1,
        unit_price_cents: bundle.bundle_price_cents ?? 0,
        image_url: bundle.image_url ?? null,
        short_description: bundle.short_description ?? null,
      },
    ])
    setAdded(bundle.id)
    setTimeout(() => setAdded(null), 1000)
  }

  function handleAdd(product: Product) {
    setPendingSelections((prev) => [
      ...prev,
      {
        product_id: product.id,
        product_name: product.name,
        quantity: 1,
        unit_price_cents: product.price_per_day_cents ?? 0,
        image_url: product.image_url ?? null,
      },
    ])
    setAdded(product.id)
    setTimeout(() => setAdded(null), 1000)
  }

  function handleClose() {
    pendingSelections.forEach((line) => onSelect(line))
    setPendingSelections([])
    setSearch('')
    setCategoryFilter('')
    setAdded(null)
    setTab('products')
    onClose()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Ajouter un article"
      size="full"
      closeOnOverlayClick={false}
      footer={
        <button
          type="button"
          onClick={handleClose}
          className="w-full sm:w-auto px-6 py-2.5 min-h-[44px] text-sm font-medium bg-gold-500 hover:bg-gold-600 text-dark-900 rounded-lg transition-colors"
        >
          {pendingSelections.length > 0
            ? `Valider (${pendingSelections.length} article${pendingSelections.length > 1 ? 's' : ''})`
            : 'Fermer'}
        </button>
      }
    >
      <div className="space-y-4">
        {/* Onglets Produits / Packs */}
        <div className="flex gap-1 bg-[var(--s2)] rounded-lg p-1">
          <button
            type="button"
            onClick={() => setTab('products')}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${tab === 'products' ? 'bg-dark-600 text-[var(--text)]' : 'text-[var(--muted)] hover:text-dark-200'}`}
          >
            Produits
          </button>
          <button
            type="button"
            onClick={() => setTab('bundles')}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors flex items-center justify-center gap-1.5 ${tab === 'bundles' ? 'bg-dark-600 text-[var(--text)]' : 'text-[var(--muted)] hover:text-dark-200'}`}
          >
            <Layers className="w-3.5 h-3.5" />
            Packs
          </button>
        </div>

        {/* Recherche + filtre catégorie */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
            <input
              type="text"
              placeholder={tab === 'products' ? 'Rechercher un produit...' : 'Rechercher un pack...'}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-9 w-full"
              autoFocus
            />
          </div>
          {tab === 'products' && (
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="input w-40"
            >
              <option value="">Toutes categories</option>
              {categories?.map((cat) => (
                <option key={cat.id} value={cat.slug}>
                  {cat.name}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Liste produits */}
        {tab === 'products' && (
          <div className="space-y-1">
            {isLoading && (
              <div className="space-y-2 animate-pulse py-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-14 bg-[var(--s2)] rounded-lg" />
                ))}
              </div>
            )}
            {!isLoading && error && (
              <ErrorState onRetry={() => refetch()} />
            )}
            {!isLoading && !error && products.length === 0 && (
              <p className="text-center text-[var(--muted)] py-8 text-sm">Aucun produit disponible</p>
            )}
            {products.map((product) => {
              const isAdded = added === product.id
              return (
                <button
                  key={product.id}
                  type="button"
                  onClick={() => handleAdd(product)}
                  className="w-full flex items-center gap-4 p-4 rounded-lg bg-[var(--s1)] hover:bg-[var(--s2)] border border-[var(--border)] hover:border-gold-500/50 transition-colors text-left"
                >
                  {product.image_url ? (
                    <img
                      src={product.image_url}
                      alt={product.name}
                      loading="lazy"
                      className="w-10 h-10 rounded object-cover flex-shrink-0"
                    />
                  ) : (
                    <div className="w-10 h-10 rounded bg-[var(--s2)] flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[var(--text)] truncate">{product.name}</p>
                    <p className="text-xs text-[var(--muted)]">{product.category}</p>
                  </div>
                  <div className="text-right flex-shrink-0 mr-1">
                    <p className="text-sm font-semibold text-[var(--text)]">
                      {formatCents(product.price_per_day_cents ?? 0)}/j
                    </p>
                    <p className={(product.available_quantity ?? 0) > 0 ? 'text-xs text-green-400' : 'text-xs text-red-400'}>
                      {product.available_quantity ?? 0} dispo
                    </p>
                  </div>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${isAdded ? 'bg-green-500' : 'bg-dark-600 hover:bg-gold-500'}`}>
                    {isAdded ? <Check className="w-4 h-4 text-white" /> : <span className="text-white text-lg leading-none">+</span>}
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {/* Liste bundles */}
        {tab === 'bundles' && (
          <div className="space-y-1">
            {bundlesLoading && (
              <div className="space-y-2 animate-pulse py-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-14 bg-[var(--s2)] rounded-lg" />
                ))}
              </div>
            )}
            {!bundlesLoading && bundlesError && (
              <ErrorState onRetry={() => refetchBundles()} />
            )}
            {!bundlesLoading && !bundlesError && bundles.length === 0 && (
              <p className="text-center text-[var(--muted)] py-8 text-sm">Aucun pack disponible</p>
            )}
            {bundles.map((bundle) => {
              const isAdded = added === bundle.id
              return (
                <button
                  key={bundle.id}
                  type="button"
                  onClick={() => handleAddBundle(bundle)}
                  className="w-full flex items-center gap-4 p-4 rounded-lg bg-[var(--s1)] hover:bg-[var(--s2)] border border-[var(--border)] hover:border-primary-500/50 transition-colors text-left"
                >
                  <div className="w-12 h-12 rounded-lg overflow-hidden bg-primary-500/10 flex items-center justify-center flex-shrink-0">
                    {bundle.image_url ? (
                      <img src={bundle.image_url} alt={bundle.name} loading="lazy" className="w-full h-full object-cover" />
                    ) : (
                      <Layers className="w-5 h-5 text-primary-400" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-[var(--text)] truncate">{bundle.name}</p>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-primary-500/15 text-primary-400 border border-primary-500/30 shrink-0">
                        Pack
                      </span>
                    </div>
                    {bundle.short_description && (
                      <p className="text-xs text-[var(--muted)] truncate mt-0.5">{bundle.short_description}</p>
                    )}
                  </div>
                  <div className="text-right flex-shrink-0 mr-1">
                    <p className="text-sm font-semibold text-[var(--text)]">
                      {formatCents(bundle.bundle_price_cents ?? 0)}
                    </p>
                    {bundle.cleaning_fee_cents > 0 && (
                      <p className="text-[10px] text-[var(--muted)]">
                        + {formatCents(bundle.cleaning_fee_cents)} nettoyage
                      </p>
                    )}
                  </div>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${isAdded ? 'bg-green-500' : 'bg-dark-600 hover:bg-primary-500'}`}>
                    {isAdded ? <Check className="w-4 h-4 text-white" /> : <span className="text-white text-lg leading-none">+</span>}
                  </div>
                </button>
              )
            })}
          </div>
        )}

        <p className="text-xs text-dark-500 text-center">
          Cliquez sur les articles pour les ajouter (qté modifiable ensuite). Fermez quand vous avez fini.
        </p>
      </div>
    </Modal>
  )
}
