import { useState } from 'react'
import { useParams, useNavigate } from '@tanstack/react-router'
import { normalizeError } from '@shared/errors/normalizer'
import {
  ArrowLeft, ChevronDown, ChevronRight, Check, Layers,
  Loader2, Package, Plus, Search, Trash2,
} from 'lucide-react'
import { ActionError } from '@shared/components/ui/ActionError'
import { useReservationDetail } from '@/api/queries/useReservations'
import { useAddReservationLine, useRemoveReservationLine } from '@/api/queries/useReservations'
import { useProductsList } from '@/api/queries/useProducts'
import { useBundlesList } from '@/api/queries/useBundles'
import { useDebounce } from '@/hooks/useDebounce'
import { formatCents, cn } from '@/lib/utils'
import type { ReservationLine } from '@/types/reservation'

type CatalogueTab = 'products' | 'bundles'

export default function ReservationLinesPage() {
  const { id } = useParams({ strict: false })
  const navigate = useNavigate()
  const reservationId = Number(id)
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [showCatalogue, setShowCatalogue] = useState(false)
  const [catalogueTab, setCatalogueTab] = useState<CatalogueTab>('products')
  const [expandedBundles, setExpandedBundles] = useState<Set<number>>(new Set())
  const debouncedSearch = useDebounce(search, 300)

  const { data: reservation, isLoading } = useReservationDetail(reservationId)
  const { data: productsData, isLoading: productsLoading } = useProductsList({
    search: debouncedSearch || undefined,
    limit: 30,
    active_only: true,
  })
  const products = productsData?.items ?? []

  const { data: bundlesData, isLoading: bundlesLoading } = useBundlesList(
    { limit: 50, active_only: true },
    showCatalogue && catalogueTab === 'bundles',
  )
  const allBundles = bundlesData?.items ?? []
  const bundles = debouncedSearch
    ? allBundles.filter((b) => b.name.toLowerCase().includes(debouncedSearch.toLowerCase()))
    : allBundles

  const addLine = useAddReservationLine()
  const removeLine = useRemoveReservationLine()

  const isDraft = reservation?.status === 'draft'
  const errHandler = (err: unknown) => setError(normalizeError(err).message || 'Erreur')

  const handleAddProduct = (productId: number) => {
    addLine.mutate(
      { reservationId, data: { product_id: productId, quantity: 1 } },
      { onError: errHandler, onSuccess: () => setError(null) },
    )
  }

  const handleAddBundle = (bundleId: number) => {
    addLine.mutate(
      { reservationId, data: { bundle_id: bundleId, quantity: 1 } },
      { onError: errHandler, onSuccess: () => setError(null) },
    )
  }

  const handleRemove = (lineId: number) => {
    removeLine.mutate({ reservationId, lineId }, { onError: errHandler })
  }

  const toggleBundleExpand = (lineId: number) => {
    setExpandedBundles((prev) => {
      const next = new Set(prev)
      if (next.has(lineId)) next.delete(lineId)
      else next.add(lineId)
      return next
    })
  }

  const addedProductIds = new Set(reservation?.lines?.map((l) => l.product_id).filter(Boolean))
  const addedBundleIds = new Set(reservation?.lines?.map((l) => l.bundle_id).filter(Boolean))

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4 animate-pulse">
        <div className="h-8 bg-dark-700 rounded w-48" />
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-4 flex gap-3">
              <div className="w-14 h-14 bg-dark-700 rounded-lg shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-dark-700 rounded w-40" />
                <div className="h-3 bg-dark-700 rounded w-24" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!reservation) {
    return (
      <div className="card text-center py-12">
        <p className="text-red-400 mb-4">Réservation introuvable.</p>
        <button onClick={() => navigate({ to: '/reservations' })} className="btn-secondary text-sm">Retour</button>
      </div>
    )
  }

  const lines = reservation.lines ?? []

  const renderLine = (line: ReservationLine) => {
    const isBundle = !!line.bundle_id && !!line.bundle
    const isExpanded = expandedBundles.has(line.id)
    const name = line.variant?.label || line.bundle?.name || line.product?.name || `Article #${line.id}`
    const imageUrl = isBundle ? line.bundle?.image_url : line.product?.image_url
    const bundleItems = isBundle ? (line.bundle?.items ?? []) : []

    return (
      <div key={line.id} className="card overflow-hidden" style={{ marginBottom: 0 }}>
        <div className="p-3 flex gap-3 items-center">
          {/* Thumbnail */}
          <div className="w-14 h-14 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
            {imageUrl ? (
              <img src={imageUrl} alt={name} className="w-full h-full object-cover" loading="lazy" />
            ) : isBundle ? (
              <Layers className="w-6 h-6 text-primary-400" />
            ) : (
              <Package className="w-6 h-6 text-dark-600" />
            )}
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium truncate">{name}</p>
              {isBundle && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-primary-500/15 text-primary-400 border border-primary-500/30 shrink-0">
                  Pack
                </span>
              )}
            </div>
            <p className="text-xs text-dark-400">
              {line.quantity} &times; {formatCents(line.unit_price_cents)}/j
              {reservation.rental_days > 1 && ` × ${reservation.rental_days}j`}
            </p>
            {isBundle && bundleItems.length > 0 && (
              <button
                type="button"
                onClick={() => toggleBundleExpand(line.id)}
                className="text-[11px] text-primary-400 hover:text-primary-300 mt-0.5 flex items-center gap-1"
              >
                {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                {bundleItems.length} article{bundleItems.length > 1 ? 's' : ''}
              </button>
            )}
          </div>

          {/* Prix + suppression */}
          <div className="text-right shrink-0">
            <p className="text-sm font-semibold text-green-400">{formatCents(line.subtotal_cents)}</p>
            {isDraft && (
              <button
                onClick={() => handleRemove(line.id)}
                disabled={removeLine.isPending}
                className="mt-1 p-1 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Items du bundle dépliés */}
        {isBundle && isExpanded && bundleItems.length > 0 && (
          <div className="border-t border-dark-700 bg-dark-800/40">
            {bundleItems.map((bi) => (
              <div
                key={bi.id}
                className="px-3 py-2 flex gap-3 items-center border-b border-dark-700/50 last:border-b-0"
              >
                <div className="w-8 h-8 rounded-md overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center ml-4">
                  {bi.product.image_url ? (
                    <img src={bi.product.image_url} alt={bi.product.name} className="w-full h-full object-cover" loading="lazy" />
                  ) : (
                    <Package className="w-3.5 h-3.5 text-dark-600" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate text-dark-200">{bi.product.name}</p>
                  {bi.product.sku && (
                    <p className="text-[10px] text-dark-500 font-mono">{bi.product.sku}</p>
                  )}
                </div>
                <span className="text-xs text-dark-400 shrink-0">
                  &times; {bi.quantity * line.quantity}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <ActionError message={error} onDismiss={() => setError(null)} />

      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate({ to: '/reservations/$id', params: { id: String(reservationId) } })}
          className="p-2 hover:bg-dark-600 rounded-lg text-dark-400 shrink-0"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-semibold truncate">{reservation.reference} — Articles</h1>
          <p className="text-xs text-dark-400">
            {reservation.customer_name} · {lines.length} article{lines.length !== 1 ? 's' : ''} · {formatCents(reservation.total_amount_cents)}
            {!isDraft && <span className="ml-2 text-amber-400">(lecture seule)</span>}
          </p>
        </div>
      </div>

      {/* Lignes actuelles */}
      {lines.length > 0 ? (
        <div className="space-y-2">
          {lines.map(renderLine)}

          <div className="flex justify-between items-center px-1 pt-2 text-base font-bold">
            <span>Total</span>
            <span className="text-green-400">{formatCents(reservation.total_amount_cents)}</span>
          </div>
        </div>
      ) : (
        <div className="card text-center py-8">
          <Package className="w-10 h-10 text-dark-600 mx-auto mb-2" />
          <p className="text-sm text-dark-400">Aucun article</p>
          {isDraft && (
            <button onClick={() => setShowCatalogue(true)} className="btn-primary btn-sm mt-3">
              <Plus className="w-4 h-4 mr-1" /> Ajouter des produits
            </button>
          )}
        </div>
      )}

      {/* Bouton ajouter */}
      {isDraft && lines.length > 0 && !showCatalogue && (
        <button
          onClick={() => setShowCatalogue(true)}
          className="w-full py-3 border-2 border-dashed border-dark-600 rounded-xl text-sm text-dark-400 hover:border-primary-500 hover:text-primary-400 transition-colors flex items-center justify-center gap-2"
        >
          <Plus className="w-4 h-4" /> Ajouter un article
        </button>
      )}

      {/* Catalogue picker inline */}
      {isDraft && showCatalogue && (
        <div className="card overflow-hidden">
          {/* Onglets + fermer */}
          <div className="p-3 border-b border-dark-600 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex gap-1 bg-dark-700 rounded-lg p-0.5">
                <button
                  type="button"
                  onClick={() => setCatalogueTab('products')}
                  className={cn(
                    'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                    catalogueTab === 'products' ? 'bg-dark-600 text-dark-50' : 'text-dark-400 hover:text-dark-200',
                  )}
                >
                  Produits
                </button>
                <button
                  type="button"
                  onClick={() => setCatalogueTab('bundles')}
                  className={cn(
                    'px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1',
                    catalogueTab === 'bundles' ? 'bg-dark-600 text-dark-50' : 'text-dark-400 hover:text-dark-200',
                  )}
                >
                  <Layers className="w-3 h-3" />
                  Packs
                </button>
              </div>
              <button onClick={() => { setShowCatalogue(false); setSearch('') }} className="text-xs text-dark-400 hover:text-dark-200">
                Fermer
              </button>
            </div>

            <div className="flex items-center gap-2">
              <Search className="w-4 h-4 text-dark-500 shrink-0" />
              <input
                type="text"
                placeholder={catalogueTab === 'products' ? 'Rechercher un produit…' : 'Rechercher un pack…'}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-dark-500"
                autoFocus
              />
            </div>
          </div>

          <div className="max-h-[360px] overflow-y-auto divide-y divide-dark-700/50">
            {/* Produits */}
            {catalogueTab === 'products' && (
              <>
                {productsLoading ? (
                  <div className="p-6 text-center">
                    <Loader2 className="w-5 h-5 animate-spin mx-auto text-dark-500" />
                  </div>
                ) : products.length === 0 ? (
                  <div className="p-6 text-center text-sm text-dark-500">
                    {debouncedSearch ? 'Aucun produit trouvé' : 'Tapez pour chercher'}
                  </div>
                ) : (
                  products.map((p) => {
                    const alreadyAdded = addedProductIds.has(p.id)
                    return (
                      <button
                        key={p.id}
                        onClick={() => !alreadyAdded && handleAddProduct(p.id)}
                        disabled={addLine.isPending || alreadyAdded}
                        className={cn(
                          'w-full flex items-center gap-3 p-3 text-left transition-colors',
                          alreadyAdded ? 'opacity-50 cursor-default' : 'hover:bg-dark-600/40',
                        )}
                      >
                        <div className="w-10 h-10 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
                          {p.image_url ? (
                            <img src={p.image_url} alt={p.name} className="w-full h-full object-cover" loading="lazy" />
                          ) : (
                            <Package className="w-4 h-4 text-dark-600" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{p.name}</p>
                          <p className="text-xs text-dark-400">
                            {formatCents(p.price_per_day_cents)}/j
                            {p.available_quantity != null && <span className="ml-1">· stock {p.available_quantity}</span>}
                          </p>
                        </div>
                        {alreadyAdded ? (
                          <Check className="w-4 h-4 text-green-400 shrink-0" />
                        ) : (
                          <Plus className="w-4 h-4 text-primary-400 shrink-0" />
                        )}
                      </button>
                    )
                  })
                )}
              </>
            )}

            {/* Packs */}
            {catalogueTab === 'bundles' && (
              <>
                {bundlesLoading ? (
                  <div className="p-6 text-center">
                    <Loader2 className="w-5 h-5 animate-spin mx-auto text-dark-500" />
                  </div>
                ) : bundles.length === 0 ? (
                  <div className="p-6 text-center text-sm text-dark-500">
                    {debouncedSearch ? 'Aucun pack trouvé' : 'Aucun pack disponible'}
                  </div>
                ) : (
                  bundles.map((b) => {
                    const alreadyAdded = addedBundleIds.has(b.id)
                    return (
                      <button
                        key={b.id}
                        onClick={() => !alreadyAdded && handleAddBundle(b.id)}
                        disabled={addLine.isPending || alreadyAdded}
                        className={cn(
                          'w-full flex items-center gap-3 p-3 text-left transition-colors',
                          alreadyAdded ? 'opacity-50 cursor-default' : 'hover:bg-dark-600/40',
                        )}
                      >
                        <div className="w-10 h-10 rounded-lg overflow-hidden bg-primary-500/10 shrink-0 flex items-center justify-center">
                          {b.image_url ? (
                            <img src={b.image_url} alt={b.name} className="w-full h-full object-cover" loading="lazy" />
                          ) : (
                            <Layers className="w-4 h-4 text-primary-400" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <p className="text-sm font-medium truncate">{b.name}</p>
                            <span className="text-[10px] px-1 py-0.5 rounded-full bg-primary-500/15 text-primary-400 border border-primary-500/30 shrink-0">
                              Pack
                            </span>
                          </div>
                          {b.short_description && (
                            <p className="text-xs text-dark-400 truncate">{b.short_description}</p>
                          )}
                        </div>
                        <div className="text-right shrink-0 mr-1">
                          <p className="text-xs font-semibold">{formatCents(b.bundle_price_cents)}</p>
                        </div>
                        {alreadyAdded ? (
                          <Check className="w-4 h-4 text-green-400 shrink-0" />
                        ) : (
                          <Plus className="w-4 h-4 text-primary-400 shrink-0" />
                        )}
                      </button>
                    )
                  })
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
