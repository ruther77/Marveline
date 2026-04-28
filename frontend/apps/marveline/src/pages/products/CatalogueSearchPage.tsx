import { PageHeader } from '@/components/PageHeader'
import { useState, useMemo } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Search, QrCode, Package } from 'lucide-react'
import { useProductsList, useCategoriesList } from '@/api/queries'
import { useDebounce } from '@/hooks/useDebounce'
import { cn, formatCents } from '@/lib/utils'
import { getStockStatus } from '@/types/product'
import { NoSearchResults, ErrorState } from '@shared/components/ui/EmptyState'
import type { StockStatus } from '@/types/product'

// ── Pastilles stock ────────────────────────────────────────────────────────

const CHIP_CONFIG: Record<StockStatus, { label: string; className: string }> = {
  in_stock:     { label: 'Disponible',   className: 'bg-green-900/40 text-green-300 border border-green-700/40' },
  low_stock:    { label: 'Faible',       className: 'bg-orange-900/40 text-orange-300 border border-orange-700/40' },
  out_of_stock: { label: 'Rupture',      className: 'bg-red-900/40 text-red-300 border border-red-700/40' },
}

const FILTER_PILLS = [
  { key: 'all',        label: 'Tous' },
  { key: 'in_stock',   label: 'Disponibles' },
  { key: 'low_stock',  label: 'Faible stock' },
  { key: 'out_of_stock', label: 'Rupture' },
] as const

type FilterKey = typeof FILTER_PILLS[number]['key']

// ── Skeleton ──────────────────────────────────────────────────────────────

function RowSkeleton() {
  return (
    <div className="flex items-center gap-4 p-4 animate-pulse">
      <div className="w-8 h-8 rounded-lg skel shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3 skel rounded w-2/3" />
        <div className="h-2 skel rounded w-1/2" />
      </div>
      <div className="h-5 w-16 skel rounded-full" />
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function CatalogueSearchPage() {
  const navigate = useNavigate()

  // Filtres
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<string>('')
  const [stockFilter, setStockFilter] = useState<FilterKey>('all')

  const debouncedSearch = useDebounce(search, 300)

  // Données
  const { data: categories = [] } = useCategoriesList()

  const { data, isLoading, isError, refetch } = useProductsList({
    limit: 200,
    active_only: true,
    search: debouncedSearch || undefined,
    category: category || undefined,
  })

  const products = useMemo(() => data?.items ?? [], [data])

  // Filtre stock côté client
  const filtered = useMemo(() => {
    if (stockFilter === 'all') return products
    return products.filter((p) => getStockStatus(p) === stockFilter)
  }, [products, stockFilter])

  // ── Rendu ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Search className="w-5 h-5 text-gold-400" />
        <PageHeader title="Recherche avancée" />
      </div>

      {/* Barre recherche + QR */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Mot-clé, référence…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-9 w-full"
          />
        </div>
        <button
          onClick={() => navigate({ to: '/catalogue/qr' })}
          className="px-4 py-2 rounded-lg border border-primary-500/25 bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 transition-colors"
          aria-label="Scanner QR"
        >
          <QrCode className="w-5 h-5" />
        </button>
      </div>

      {/* Sélecteurs catégorie + état */}
      <div className="flex gap-2">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="input flex-1 text-sm"
        >
          <option value="">Toutes categories</option>
          {categories.filter((c) => c.parent_id != null).map((c) => (
            <option key={c.slug} value={c.slug}>{c.name}</option>
          ))}
        </select>
        <select
          value={stockFilter}
          onChange={(e) => setStockFilter(e.target.value as FilterKey)}
          className="input flex-1 text-sm"
        >
          <option value="all">Tous stocks</option>
          <option value="in_stock">Disponible</option>
          <option value="low_stock">Stock faible</option>
          <option value="out_of_stock">Rupture</option>
        </select>
      </div>

      {/* Pills filtre rapide */}
      <div className="flex gap-2 flex-wrap pb-1 lg:flex-nowrap lg:overflow-x-auto">
        {FILTER_PILLS.map((pill) => (
          <button
            key={pill.key}
            onClick={() => setStockFilter(pill.key)}
            className={cn(
              'px-4 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors',
              stockFilter === pill.key
                ? 'bg-primary-500 text-white'
                : 'bg-dark-900 text-dark-400 hover:bg-dark-600',
            )}
          >
            {pill.label}
          </button>
        ))}
      </div>

      {/* Liste résultats */}
      {isLoading ? (
        <div className="card divide-y divide-dark-600">
          {Array.from({ length: 8 }).map((_, i) => (
            <RowSkeleton key={i} />
          ))}
        </div>
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : filtered.length === 0 ? (
        <NoSearchResults
          searchTerm={search || undefined}
          onClear={() => { setSearch(''); setStockFilter('all'); setCategory('') }}
        />
      ) : (
        <div className="card divide-y divide-dark-600">
          {filtered.map((product) => {
            const status = getStockStatus(product)
            const chip = CHIP_CONFIG[status]

            return (
              <button
                key={product.id}
                onClick={() => navigate({ to: '/catalogue/products/$id' as never, params: { id: String(product.id) } as never })}
                className="flex items-center gap-4 p-4 w-full text-left hover:bg-dark-600/50 transition-colors"
              >
                {/* Icône */}
                <div className="w-8 h-8 rounded-lg bg-dark-950 flex items-center justify-center shrink-0">
                  {product.image_url ? (
                    <img src={product.image_url} alt="" className="w-8 h-8 rounded-lg object-cover" />
                  ) : (
                    <Package className="w-4 h-4 text-dark-500" />
                  )}
                </div>

                {/* Infos */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{product.name}</p>
                  <p className="text-xs text-dark-400">
                    {formatCents(product.price_per_day_cents)} /j · {product.available_quantity} dispo
                    {product.sku ? ` · ${product.sku}` : ''}
                  </p>
                </div>

                {/* Pastille stock */}
                <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium shrink-0', chip.className)}>
                  {chip.label}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {/* Compteur résultats */}
      {!isLoading && !isError && filtered.length > 0 && (
        <p className="text-xs text-dark-500 text-center">{filtered.length} produit{filtered.length > 1 ? 's' : ''}</p>
      )}
    </div>
  )
}
