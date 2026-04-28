import { useState, useMemo } from 'react'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { useProductsList, useInventorySummary, useProductsStock, useCategoriesList } from '@/api/queries'
import { useOperationsSummary } from '@/api/queries/useOperations'
import { useStockCoverage } from '@/api/queries/useStock'
import { ErrorState, NoData, NoSearchResults } from '@shared/components/ui/EmptyState'
import { StockLevelBar } from '@shared/components/ui'
import {
  Search,
  Package,
  Truck,
  RotateCcw,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  BarChart3,
  Sliders,
  ExternalLink,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { getStockStatus } from '@/types/product'
import type { ProductStockDetail } from '@/types'
import {
  STOCK_ITEM_STATUS_LABELS as STATUS_LABELS,
  STOCK_ITEM_STATUS_COLORS as STATUS_COLORS,
} from '@/lib/constants'
import { useDebounce } from '@/hooks/useDebounce'
import { useHasScope } from '@/hooks/useHasScope'

// ── Types ────────────────────────────────────────────────────────────────────

type StatusKey = keyof typeof STATUS_LABELS
type StockFilter = 'all' | 'in_stock' | 'low_stock' | 'out_of_stock'

const FILTER_PILLS: { key: StockFilter; label: string; dot?: string }[] = [
  { key: 'all', label: 'Tous' },
  { key: 'in_stock', label: 'En stock', dot: 'bg-green-500' },
  { key: 'low_stock', label: 'Faible', dot: 'bg-amber-500' },
  { key: 'out_of_stock', label: 'Rupture', dot: 'bg-red-500' },
]

const PAGE_SIZE = 12
const URGENCY_ORDER: Record<string, number> = { out_of_stock: 0, low_stock: 1, in_stock: 2 }

// ── Skeleton ─────────────────────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div className="card p-4 animate-pulse space-y-3">
      <div className="flex gap-3">
        <div className="w-14 h-14 bg-dark-100/10 rounded-xl shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-dark-100/10 rounded w-3/4" />
          <div className="h-3 bg-dark-100/10 rounded w-1/3" />
        </div>
      </div>
      <div className="h-2 bg-dark-100/10 rounded-full" />
      <div className="flex gap-2">
        <div className="h-5 bg-dark-100/10 rounded-full w-16" />
        <div className="h-5 bg-dark-100/10 rounded-full w-14" />
      </div>
    </div>
  )
}

function PageSkeleton() {
  return (
    <div className="space-y-4">
      <div className="h-11 bg-dark-100/10 rounded-xl animate-pulse" />
      <div className="flex gap-2 animate-pulse">
        <div className="h-7 bg-dark-100/10 rounded-full w-20" />
        <div className="h-7 bg-dark-100/10 rounded-full w-20" />
        <div className="h-7 bg-dark-100/10 rounded-full w-20" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)}
      </div>
    </div>
  )
}

// ── Product detail expand ────────────────────────────────────────────────────

function ProductExpand({
  product,
  detail,
  coverageData,
}: {
  product: { id: number; name: string; sku: string; available_quantity: number; stock_quantity: number }
  detail?: ProductStockDetail
  coverageData?: { days_of_coverage: number | null; rotation_rate: number; movements_30d: number; status: string }
}) {
  const navigate = useNavigate()
  const canAdjust = useHasScope('stock:adjust')

  return (
    <div className="mt-3 space-y-3 pt-3">
      {/* Status badges */}
      {detail && (
        <div className="flex flex-wrap gap-1.5">
          {(['available', 'reserved', 'on_location', 'damaged', 'in_repair'] as StatusKey[]).map((status) => {
            const count = detail[`qty_${status}` as keyof ProductStockDetail] as number
            if (count === 0) return null
            return (
              <span
                key={status}
                className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', STATUS_COLORS[status])}
              >
                {count} {STATUS_LABELS[status]}
              </span>
            )
          })}
        </div>
      )}

      {/* Coverage + rotation (from /stock/coverage data) */}
      {coverageData && (
        <div className="flex items-center gap-4 text-xs text-dark-400">
          <span className="flex items-center gap-1">
            <BarChart3 className="w-3 h-3" />
            Couverture :
            <span className={cn(
              'font-medium',
              coverageData.status === 'critical' ? 'text-red-400' :
              coverageData.status === 'low' ? 'text-amber-400' :
              'text-green-400',
            )}>
              {coverageData.days_of_coverage != null ? `${Math.round(coverageData.days_of_coverage)}j` : '∞'}
            </span>
          </span>
          <span>
            Rotation : <span className="text-dark-200 font-medium">{Math.round(coverageData.rotation_rate)}%</span>
          </span>
          <span>
            {coverageData.movements_30d} mvts/30j
          </span>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        {detail && detail.items.length > 0 && (
          <Link
            to="/stock/items/$id"
            params={{ id: `${product.id}-${detail.items[0].id}` }}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-dark-100/5 hover:bg-dark-100/10 rounded-xl transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
            Voir {detail.items.length} unité{detail.items.length > 1 ? 's' : ''}
          </Link>
        )}
        {canAdjust && (
          <button
            onClick={() => navigate({ to: '/stock/adjustments', search: { product_id: product.id } })}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-dark-100/5 hover:bg-dark-100/10 rounded-xl transition-colors"
          >
            <Sliders className="w-3 h-3" />
            Ajuster
          </button>
        )}
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function InventoryPage() {
  const navigate = useNavigate()
  const { q = '', stock = 'all', category = '', page: urlPage = 1 } = useSearch({ strict: false }) as {
    q: string; stock: string; category: string; page: number
  }

  const search = q
  const setSearch = (v: string) => navigate({ search: (prev: Record<string, unknown>) => ({ ...prev, q: v || undefined, page: 1 }) })
  const statusFilter = (stock || 'all') as StockFilter
  const setStatusFilter = (v: StockFilter) => navigate({ search: (prev: Record<string, unknown>) => ({ ...prev, stock: v === 'all' ? undefined : v, page: 1 }) })
  const categoryFilter = category || null
  const setCategoryFilter = (v: string | null) => navigate({ search: (prev: Record<string, unknown>) => ({ ...prev, category: v || undefined, page: 1 }) })
  const page = urlPage
  const setPage = (p: number) => navigate({ search: (prev: Record<string, unknown>) => ({ ...prev, page: p }) })
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const debouncedSearch = useDebounce(search, 300)

  // Data
  const { data: summary } = useInventorySummary()
  const { data: opsSummary } = useOperationsSummary()
  const { data: coverageResponse } = useStockCoverage()
  const { data: categories } = useCategoriesList()

  const hasStockFilter = statusFilter !== 'all'

  const { data, isLoading, error, refetch } = useProductsList({
    skip: hasStockFilter ? 0 : (page - 1) * PAGE_SIZE,
    limit: hasStockFilter ? 500 : PAGE_SIZE,
    active_only: true,
    search: debouncedSearch || undefined,
    category: categoryFilter || undefined,
  })

  const products = data?.items || []
  const uniqueCatégories = summary?.categories ?? []

  const allFilteredProducts = useMemo(() =>
    products
      .filter((p) => {
        if (statusFilter !== 'all' && getStockStatus(p) !== statusFilter) return false
        return true
      })
      .sort((a, b) => (URGENCY_ORDER[getStockStatus(a)] ?? 2) - (URGENCY_ORDER[getStockStatus(b)] ?? 2)),
    [products, statusFilter],
  )

  const filteredTotal = hasStockFilter ? allFilteredProducts.length : (data?.total ?? 0)
  const filteredProducts = hasStockFilter
    ? allFilteredProducts.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
    : allFilteredProducts

  const detailProductIds = filteredProducts.map((p) => p.id)
  const { data: stockDetails = [] } = useProductsStock(detailProductIds)
  const stockDetailMap = useMemo(() => {
    const map: Record<number, ProductStockDetail> = {}
    stockDetails.forEach((d) => { map[d.product_id] = d })
    return map
  }, [stockDetails])

  // Coverage map for expand inline
  const coverageMap = useMemo(() => {
    const items = coverageResponse?.items ?? []
    const map: Record<number, { days_of_coverage: number | null; rotation_rate: number; movements_30d: number; status: string }> = {}
    items.forEach((item: { product_id: number; days_of_coverage: number | null; rotation_rate: number; movements_30d: number; status: string }) => {
      map[item.product_id] = item
    })
    return map
  }, [coverageResponse])

  // Operations chips
  const departuresCount = opsSummary?.departures?.length ?? 0
  const returnsCount = opsSummary?.returns_pending?.length ?? 0
  const overdueCount = opsSummary?.returns_overdue?.length ?? 0

  const hasActiveFilters = search !== '' || statusFilter !== 'all' || categoryFilter !== null
  const clearFilters = () => {
    setSearch('')
    setStatusFilter('all')
    setCategoryFilter(null)
    setPage(1)
  }

  const toggleExpand = (id: number) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  if (isLoading && page === 1) {
    return (
      <div className="max-w-2xl lg:max-w-7xl mx-auto">
        <PageSkeleton />
      </div>
    )
  }

  return (
    <div className="max-w-2xl lg:max-w-7xl mx-auto space-y-4">

      {/* ── Search ────────────────────────────────────────────────── */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
        <input
          type="text"
          placeholder="Rechercher un produit..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          className="input w-full pl-12 py-3 text-base rounded-xl"
        />
      </div>

      {/* ── Context chips ─────────────────────────────────────────── */}
      <div className="flex items-center gap-2 flex-wrap lg:flex-nowrap lg:overflow-x-auto lg:scrollbar-hide">
        <Link
          to="/stock/inventory"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 whitespace-nowrap shrink-0 hover:bg-emerald-500/20 transition-colors"
        >
          <ClipboardCheck className="w-3.5 h-3.5" />
          Inventaire physique
        </Link>
        {departuresCount > 0 && (
          <Link
            to="/operations"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 whitespace-nowrap shrink-0 hover:bg-blue-500/20 transition-colors"
          >
            <Truck className="w-3.5 h-3.5" />
            {departuresCount} départ{departuresCount > 1 ? 's' : ''}
          </Link>
        )}
        {returnsCount > 0 && (
          <Link
            to="/operations"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-orange-500/10 text-orange-400 border border-orange-500/20 whitespace-nowrap shrink-0 hover:bg-orange-500/20 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            {returnsCount} retour{returnsCount > 1 ? 's' : ''}
          </Link>
        )}
        {overdueCount > 0 && (
          <Link
            to="/operations"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20 whitespace-nowrap shrink-0 hover:bg-red-500/20 transition-colors animate-pulse"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            {overdueCount} retard{overdueCount > 1 ? 's' : ''}
          </Link>
        )}
        {departuresCount === 0 && returnsCount === 0 && overdueCount === 0 && (
          <span className="text-xs text-dark-500">Aucune opération en cours</span>
        )}
      </div>

      {/* ── Filter pills ──────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-1.5">
        {FILTER_PILLS.map(({ key, label, dot }) => (
          <button
            key={key}
            onClick={() => { setStatusFilter(key); setPage(1) }}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all',
              statusFilter === key
                ? 'bg-primary-500 text-white'
                : 'bg-dark-100/5 text-dark-400 hover:bg-dark-100/10',
            )}
          >
            {dot && <span className={cn('w-1.5 h-1.5 rounded-full', dot)} />}
            {label}
          </button>
        ))}

        {/* Category select */}
        {(categories?.length ?? 0) >= 2 && (
          <>
            <span className="w-px h-5 bg-dark-200/20 self-center mx-1" />
            <select
              value={categoryFilter ?? ''}
              onChange={(e) => { setCategoryFilter(e.target.value || null); setPage(1) }}
              className={cn(
                'px-3 py-1.5 rounded-full text-xs font-medium transition-all appearance-none pr-7 bg-no-repeat bg-[length:12px] bg-[right_8px_center]',
                categoryFilter
                  ? 'bg-gold-500 text-dark-900'
                  : 'bg-dark-900 text-dark-400 border border-dark-700',
              )}
              style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath d='M3 4.5l3 3 3-3' fill='none' stroke='%23999' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E\")" }}
            >
              <option value="">Catégorie…</option>
              {(categories ?? []).filter((c) => c.parent_id != null).map((cat) => (
                <option key={cat.slug} value={cat.slug}>{cat.name}</option>
              ))}
            </select>
          </>
        )}

        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="px-3 py-1.5 rounded-full text-xs font-medium text-dark-500 hover:text-dark-300 transition-colors"
          >
            Effacer
          </button>
        )}
      </div>

      {/* ── Error ─────────────────────────────────────────────────── */}
      {error && <ErrorState onRetry={() => refetch()} />}

      {/* ── Product grid ──────────────────────────────────────────── */}
      {!isLoading && filteredTotal === 0 && (
        hasActiveFilters
          ? <NoSearchResults searchTerm={search || undefined} onClear={clearFilters} />
          : <NoData />
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {filteredProducts.map((product) => {
          const stockStatus = getStockStatus(product)
          const isExpanded = expandedId === product.id
          const detail = stockDetailMap[product.id]
          const coverage = coverageMap[product.id]

          return (
            <div
              key={product.id}
              className={cn(
                'card p-3 transition-all cursor-pointer col-span-1',
                isExpanded && 'col-span-2 md:col-span-3 ring-1 ring-primary-500/30',
                !isExpanded && stockStatus === 'out_of_stock' && 'ring-1 ring-red-500/20',
                !isExpanded && stockStatus === 'low_stock' && 'ring-1 ring-amber-500/20',
              )}
              onClick={() => toggleExpand(product.id)}
            >
              <div className="flex gap-3">
                {/* Image */}
                <div className="w-14 h-14 rounded-xl overflow-hidden bg-dark-100/5 shrink-0 flex items-center justify-center">
                  {product.image_url ? (
                    <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" loading="lazy" />
                  ) : (
                    <Package className="w-5 h-5 text-dark-500" />
                  )}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-1">
                    <p className="font-medium text-sm truncate">{product.name}</p>
                    {isExpanded
                      ? <ChevronUp className="w-4 h-4 text-dark-400 shrink-0" />
                      : <ChevronDown className="w-4 h-4 text-dark-400 shrink-0" />
                    }
                  </div>
                  <p className="text-[11px] text-dark-500 font-mono">{product.sku}</p>
                  {product.category && (
                    <p className="text-[11px] text-dark-400 mt-0.5">{product.category}</p>
                  )}
                </div>
              </div>

              {/* Stock bar */}
              <div className="mt-2.5">
                <StockLevelBar available={product.available_quantity} total={product.stock_quantity} size="sm" />
              </div>

              {/* Expand */}
              {isExpanded && (
                <ProductExpand
                  product={product}
                  detail={detail}
                  coverageData={coverage}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* ── Pagination ────────────────────────────────────────────── */}
      {filteredTotal > PAGE_SIZE && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-dark-500">
            {page}/{Math.ceil(filteredTotal / PAGE_SIZE)} · {filteredTotal} produits
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-xs rounded-lg bg-dark-700 text-dark-300 hover:bg-dark-600 disabled:opacity-30"
            >
              Préc.
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={page >= Math.ceil(filteredTotal / PAGE_SIZE)}
              className="px-3 py-1.5 text-xs rounded-lg bg-dark-700 text-dark-300 hover:bg-dark-600 disabled:opacity-30"
            >
              Suiv.
            </button>
          </div>
        </div>
      )}

      {/* ── FAB Inventaire ────────────────────────────────────────── */}
      <Link
        to="/stock/inventory"
        className="fixed right-4 z-40 flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-semibold px-4 py-3 rounded-xl shadow-lg shadow-gold-500/20 active:scale-95 transition-all duration-200"
        style={{ bottom: 'calc(var(--nav-offset, 80px) + 16px)' }}
      >
        <ClipboardCheck className="w-5 h-5" />
        <span className="text-sm">Inventaire</span>
      </Link>
    </div>
  )
}
