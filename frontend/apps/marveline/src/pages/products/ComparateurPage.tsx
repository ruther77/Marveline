import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { GitCompare, X, Search, Check, Package, ArrowLeftRight } from 'lucide-react'
import { useProductsList, useBundlesList, useBundleDetail } from '@/api/queries'
import { useQueries } from '@tanstack/react-query'
import { useDebounce } from '@/hooks/useDebounce'
import { cn } from '@/lib/utils'
import type { Product, BundleWithItems } from '@/types/product'
import { CATEGORY_LABELS } from '@/types/product'
import type { Bundle } from '@/types/product'
import { queryKeys } from '@/api/queries/keys'
import { bundlesApi } from '@/api/bundles'
import { ErrorState } from '@shared/components/ui/EmptyState'

// ── Constantes ────────────────────────────────────────────────────────────

type CompareMode = 'products' | 'bundles'

const CONDITION_LABELS: Record<string, string> = {
  neuf: 'Neuf',
  bon: 'Bon état',
  use: 'Usé',
  hors_service: 'Hors service',
}

const PRODUCT_ROWS: { label: string; render: (p: Product) => string }[] = [
  { label: 'SKU', render: (p) => p.sku },
  { label: 'Catégorie', render: (p) => CATEGORY_LABELS[p.category] ?? p.category },
  { label: 'Prix / jour', render: (p) => `${p.price_per_day_euros.toFixed(2)} €` },
  { label: 'Stock total', render: (p) => String(p.stock_quantity) },
  { label: 'Disponible', render: (p) => String(p.available_quantity) },
  { label: 'État', render: (p) => CONDITION_LABELS[p.condition] ?? p.condition },
  { label: 'TVA', render: (p) => `${(p.tva_rate * 100).toFixed(0)} %` },
]

const BUNDLE_ROWS: { label: string; render: (b: BundleWithItems) => string }[] = [
  { label: 'Nb produits', render: (b) => `${b.total_items} article${b.total_items > 1 ? 's' : ''}` },
  { label: 'Prix pack', render: (b) => `${(b.bundle_price_euros ?? 0).toFixed(2)} €` },
  { label: 'Prix individuel', render: (b) => `${(b.individual_price_euros ?? 0).toFixed(2)} €` },
  {
    label: 'Économie',
    render: (b) => {
      const pct = b.individual_price_euros > 0
        ? Math.round(((b.savings_euros ?? 0) / b.individual_price_euros) * 100)
        : 0
      return b.savings_euros > 0 ? `${b.savings_euros.toFixed(2)} € (−${pct} %)` : '—'
    },
  },
  { label: 'Nettoyage', render: (b) => b.cleaning_fee_euros ? `${b.cleaning_fee_euros.toFixed(2)} €` : 'Inclus' },
  {
    label: 'Contenu',
    render: (b) => b.items.length > 0
      ? b.items.map((i) => `${i.quantity}× ${i.product.name}`).join(', ')
      : '—',
  },
  { label: 'Mis en avant', render: (b) => b.featured ? 'Oui' : 'Non' },
  { label: 'Statut', render: (b) => b.is_active ? 'Actif' : 'Inactif' },
]

const MAX_COMPARE = 4

// ── Composants internes ───────────────────────────────────────────────────

function ModeToggle({ mode, onChange }: { mode: CompareMode; onChange: (m: CompareMode) => void }) {
  return (
    <div className="flex rounded-xl border border-dark-600 overflow-hidden">
      <button
        onClick={() => onChange('products')}
        className={cn(
          'flex-1 px-5 py-2 text-sm font-medium transition-colors',
          mode === 'products'
            ? 'bg-primary-500 text-white'
            : 'bg-dark-900 text-dark-400 hover:text-dark-200'
        )}
      >
        Produits
      </button>
      <button
        onClick={() => onChange('bundles')}
        className={cn(
          'flex-1 px-5 py-2 text-sm font-medium transition-colors',
          mode === 'bundles'
            ? 'bg-primary-500 text-white'
            : 'bg-dark-900 text-dark-400 hover:text-dark-200'
        )}
      >
        Packs
      </button>
    </div>
  )
}

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-primary-500/15 text-primary-300 border border-primary-500/30 rounded-full text-sm">
      <span className="truncate max-w-[140px]">{label}</span>
      <button onClick={onRemove} className="hover:text-primary-100 shrink-0">
        <X className="w-3.5 h-3.5" />
      </button>
    </span>
  )
}

function SelectableRow<T extends { id: number }>({
  item,
  label,
  sub,
  imageUrl,
  isSelected,
  disabled,
  onToggle,
}: {
  item: T
  label: string
  sub?: string
  imageUrl?: string | null
  isSelected: boolean
  disabled: boolean
  onToggle: (item: T) => void
}) {
  return (
    <button
      onClick={() => !disabled && onToggle(item)}
      className={cn(
        'w-full flex items-center gap-3 px-4 py-3 text-left transition-colors',
        isSelected && 'bg-primary-500/10',
        disabled && !isSelected && 'opacity-30 cursor-not-allowed',
        !isSelected && !disabled && 'hover:bg-dark-600',
      )}
    >
      <div
        className={cn(
          'w-5 h-5 rounded border flex items-center justify-center shrink-0 transition-colors',
          isSelected ? 'bg-primary-500 border-primary-500' : 'border-dark-500',
        )}
      >
        {isSelected && <Check className="w-3 h-3 text-white" />}
      </div>
      <div className="w-8 h-8 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
        {imageUrl ? (
          <img src={imageUrl} alt={label} className="w-full h-full object-cover" />
        ) : (
          <Package className="w-4 h-4 text-dark-500" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium truncate">{label}</p>
        {sub && <p className="text-xs text-dark-500 truncate">{sub}</p>}
      </div>
    </button>
  )
}

function CompareTable<T extends { id: number; name: string; image_url?: string | null }>({
  items,
  rows,
}: {
  items: T[]
  rows: { label: string; render: (item: T) => string }[]
}) {
  if (items.length < 2) {
    return (
      <div className="card flex flex-col items-center justify-center h-52 gap-3">
        <ArrowLeftRight className="w-8 h-8 text-dark-600" />
        <p className="text-dark-400 text-sm">Sélectionnez au moins 2 éléments</p>
      </div>
    )
  }

  return (
    <div className="card p-0 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-dark-600">
            <th className="text-left px-4 py-4 text-dark-400 font-medium w-36 sticky left-0 bg-dark-900 z-10">Critère</th>
            {items.map((item) => (
              <th key={item.id} className="px-4 py-4 text-center min-w-[150px]">
                <div className="flex flex-col items-center gap-2">
                  <div className="w-12 h-12 rounded-lg overflow-hidden bg-dark-950 flex items-center justify-center">
                    {item.image_url ? (
                      <img src={item.image_url} alt={item.name} loading="lazy" className="w-full h-full object-cover" />
                    ) : (
                      <Package className="w-5 h-5 text-dark-500" />
                    )}
                  </div>
                  <span className="font-medium text-xs text-center leading-tight max-w-[140px]">{item.name}</span>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.label} className={i % 2 === 0 ? 'bg-dark-900/40' : ''}>
              <td className="px-4 py-3 text-dark-400 font-medium sticky left-0 bg-inherit z-10">{row.label}</td>
              {items.map((item) => (
                <td key={item.id} className="px-4 py-3 text-center text-dark-200">
                  {row.render(item)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Page principale ───────────────────────────────────────────────────────

export default function ComparateurPage() {
  const [mode, setMode] = useState<CompareMode>('products')
  const [search, setSearch] = useState('')
  const [selectedProducts, setSelectedProducts] = useState<Product[]>([])
  const [selectedBundles, setSelectedBundles] = useState<Bundle[]>([])
  const debouncedSearch = useDebounce(search, 300)

  const { data: productsData, isLoading: productsLoading, error: productsError, refetch: refetchProducts } =
    useProductsList({ limit: 100, search: debouncedSearch || undefined, active_only: true }, mode === 'products')

  const { data: bundlesData, isLoading: bundlesLoading, error: bundlesError, refetch: refetchBundles } =
    useBundlesList({ limit: 100, active_only: true }, mode === 'bundles')

  // Fetch détails enrichis (BundleWithItems) pour chaque pack sélectionné
  const bundleDetailQueries = useQueries({
    queries: selectedBundles.map((b) => ({
      queryKey: queryKeys.bundles.detail(b.id),
      queryFn: () => bundlesApi.getBundle(b.id),
      staleTime: 60_000,
    })),
  })
  const enrichedBundles: BundleWithItems[] = bundleDetailQueries
    .filter((q) => q.data != null)
    .map((q) => q.data)

  const products = productsData?.items ?? []
  const bundles = bundlesData?.items ?? []

  // Filtrage bundles cote client par nom/description
  const filteredBundles = debouncedSearch
    ? bundles.filter((b) => `${b.name} ${b.description ?? ''}`.toLowerCase().includes(debouncedSearch.toLowerCase()))
    : bundles

  const toggleProduct = (p: Product) => {
    setSelectedProducts((prev) => {
      if (prev.find((x) => x.id === p.id)) return prev.filter((x) => x.id !== p.id)
      if (prev.length >= MAX_COMPARE) return prev
      return [...prev, p]
    })
  }

  const toggleBundle = (b: Bundle) => {
    setSelectedBundles((prev) => {
      if (prev.find((x) => x.id === b.id)) return prev.filter((x) => x.id !== b.id)
      if (prev.length >= MAX_COMPARE) return prev
      return [...prev, b]
    })
  }

  const handleModeChange = (m: CompareMode) => {
    setMode(m)
    setSearch('')
  }

  const selected = mode === 'products' ? selectedProducts : selectedBundles
  const isLoading = mode === 'products' ? productsLoading : bundlesLoading
  const error = mode === 'products' ? productsError : bundlesError
  const refetch = mode === 'products' ? refetchProducts : refetchBundles

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-500/10 flex items-center justify-center">
            <GitCompare className="w-5 h-5 text-primary-400" />
          </div>
          <PageHeader title="Comparateur" subtitle="Jusqu'à {MAX_COMPARE} éléments côte à côte" />
        </div>
        <ModeToggle mode={mode} onChange={handleModeChange} />
      </div>

      {/* Chips sélection */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {mode === 'products'
            ? selectedProducts.map((p) => (
                <Chip key={p.id} label={p.name} onRemove={() => toggleProduct(p)} />
              ))
            : selectedBundles.map((b) => (
                <Chip key={b.id} label={b.name} onRemove={() => toggleBundle(b)} />
              ))}
        </div>
      )}

      {/* Layout 2 colonnes */}
      <div className="grid md:grid-cols-[300px_1fr] gap-5">
        {/* Panneau sélection */}
        <div className="card p-0 overflow-hidden flex flex-col" style={{ maxHeight: 'min(600px, 70vh)' }}>
          <div className="p-3 border-b border-dark-600">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={mode === 'products' ? 'Rechercher un produit…' : 'Rechercher un pack…'}
                className="w-full pl-9 pr-4 py-2 bg-dark-900 text-dark-50 text-sm rounded-lg border border-dark-600 focus:outline-none focus:border-primary-500/60 placeholder:text-dark-500"
              />
            </div>
            <p className="text-xs text-dark-500 mt-2">{selected.length}/{MAX_COMPARE} sélectionnés</p>
          </div>

          <div className="overflow-y-auto flex-1 divide-y divide-dark-600/50">
            {isLoading ? (
              <div className="animate-pulse divide-y divide-dark-600/50">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3 px-4 py-3">
                    <div className="w-5 h-5 skel rounded shrink-0" />
                    <div className="w-8 h-8 skel rounded-lg shrink-0" />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-3 skel rounded w-28" />
                      <div className="h-2 skel rounded w-16" />
                    </div>
                  </div>
                ))}
              </div>
            ) : error ? (
              <ErrorState onRetry={() => refetch()} />
            ) : mode === 'products' ? (
              products.length === 0 ? (
                <div className="p-8 text-center text-dark-500 text-sm">Aucun produit trouvé</div>
              ) : (
                products.map((p) => (
                  <SelectableRow
                    key={p.id}
                    item={p}
                    label={p.name}
                    sub={`${p.sku} · ${p.price_per_day_euros.toFixed(2)} €/j`}
                    imageUrl={p.image_url}
                    isSelected={selectedProducts.some((x) => x.id === p.id)}
                    disabled={!selectedProducts.some((x) => x.id === p.id) && selectedProducts.length >= MAX_COMPARE}
                    onToggle={toggleProduct}
                  />
                ))
              )
            ) : (
              filteredBundles.length === 0 ? (
                <div className="p-8 text-center text-dark-500 text-sm">Aucun pack trouvé</div>
              ) : (
                filteredBundles.map((b) => (
                  <SelectableRow
                    key={b.id}
                    item={b}
                    label={b.name}
                    sub={`${(b.bundle_price_euros ?? 0).toFixed(2)} € / évén.`}
                    imageUrl={b.image_url}
                    isSelected={selectedBundles.some((x) => x.id === b.id)}
                    disabled={!selectedBundles.some((x) => x.id === b.id) && selectedBundles.length >= MAX_COMPARE}
                    onToggle={toggleBundle}
                  />
                ))
              )
            )}
          </div>
        </div>

        {/* Tableau comparaison */}
        {mode === 'products' ? (
          <CompareTable items={selectedProducts} rows={PRODUCT_ROWS} />
        ) : (
          <CompareTable items={enrichedBundles} rows={BUNDLE_ROWS} />
        )}
      </div>
    </div>
  )
}
