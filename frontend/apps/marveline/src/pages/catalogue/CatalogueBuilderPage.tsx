import { PageHeader } from '@/components/PageHeader'
import { useState, useEffect } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Search, Plus, Minus, Trash2, ShoppingCart, FileText } from 'lucide-react'
import { useProductsList, useCategoriesList } from '@/api/queries'
import { useCartStore, useCartTotals, useCartLine } from '@/stores/cartStore'
import type { Product } from '@/types/product'

// ============================================
// Ligne panier — sous-composant
// ============================================

function CartLineRow({ product_id }: { product_id: number }) {
  const line = useCartLine(product_id)
  const updateLine = useCartStore((s) => s.updateLine)
  const removeLine = useCartStore((s) => s.removeLine)

  if (!line) return null

  return (
    <div className="flex items-center gap-4 p-4 rounded-lg card-inner">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-dark-100 truncate">{line.product_name}</p>
        <p className="text-xs text-dark-400">
          {(line.unit_price_cents / 100).toFixed(2)} €/j
        </p>
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() =>
            updateLine(line.id, { quantity: Math.max(1, line.quantity - 1) })
          }
          className="p-1 rounded hover:bg-dark-600 text-dark-400 hover:text-dark-100 transition-colors"
        >
          <Minus className="w-3 h-3" />
        </button>
        <span className="w-8 text-center text-sm font-medium text-dark-100">
          {line.quantity}
        </span>
        <button
          onClick={() =>
            updateLine(line.id, {
              quantity: Math.min(line.quantity + 1, line.available_quantity),
            })
          }
          className="p-1 rounded hover:bg-dark-600 text-dark-400 hover:text-dark-100 transition-colors"
        >
          <Plus className="w-3 h-3" />
        </button>
      </div>
      <div className="text-right w-20 flex-shrink-0">
        <p className="text-sm font-semibold text-dark-100">
          {(line.subtotal_cents / 100).toFixed(2)} €
        </p>
      </div>
      <button
        onClick={() => removeLine(line.id)}
        className="p-1 rounded hover:bg-red-900/30 text-dark-500 hover:text-red-400 transition-colors"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  )
}

// ============================================
// Carte produit catalogue — sous-composant
// ============================================

function ProductCard({ product }: { product: Product }) {
  const addLine = useCartStore((s) => s.addLine)
  const hasProduct = useCartStore((s) => s.hasProduct)
  const inCart = hasProduct(product.id)

  function handleAdd() {
    addLine({
      product_id: product.id,
      product_name: product.name,
      quantity: 1,
      unit_price_cents: product.price_per_day_cents,
      available_quantity: product.available_quantity,
    })
  }

  return (
    <div className="flex items-center gap-4 p-4 rounded-lg card-inner hover:border-dark-600 transition-colors">
      {product.image_url ? (
        <img
          src={product.image_url}
          alt={product.name}
          loading="lazy"
          className="w-10 h-10 rounded object-cover flex-shrink-0"
        />
      ) : (
        <div className="w-10 h-10 rounded skel flex-shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-dark-100 truncate">{product.name}</p>
        <p className="text-xs text-dark-400">{product.category}</p>
      </div>
      <div className="text-right flex-shrink-0 mr-2">
        <p className="text-sm font-semibold text-dark-100">
          {(product.price_per_day_cents / 100).toFixed(2)} €/j
        </p>
        <p
          className={
            product.available_quantity > 0 ? 'text-xs text-green-400' : 'text-xs text-red-400'
          }
        >
          {product.available_quantity} dispo
        </p>
      </div>
      <button
        onClick={handleAdd}
        disabled={product.available_quantity === 0}
        className={
          inCart
            ? 'p-2 rounded-lg bg-primary-900/40 text-primary-400 border border-primary-700 hover:bg-primary-900/60 transition-colors'
            : 'p-2 rounded-lg bg-dark-900 text-dark-300 hover:bg-dark-600 hover:text-dark-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed'
        }
        title={inCart ? 'Ajouter une unité de plus' : 'Ajouter au panier'}
      >
        <Plus className="w-4 h-4" />
      </button>
    </div>
  )
}

// ============================================
// Page principale
// ============================================

export default function CatalogueBuilderPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  const lines = useCartStore((s) => s.lines)
  const clearLines = useCartStore((s) => s.clearLines)
  const setMode = useCartStore((s) => s.setMode)
  const { total_cents, line_count } = useCartTotals()

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  const { data: productsData, isLoading, error: queryError, refetch } = useProductsList({
    search: debouncedSearch || undefined,
    category: categoryFilter || undefined,
    available_only: true,
    limit: 50,
  })

  const { data: categories } = useCategoriesList(true)

  const products = productsData?.items ?? []

  function handleCreateDevis() {
    setMode('devis')
    navigate({ to: '/devis/new' })
  }

  function handleCreateReservation() {
    setMode('reservation')
    navigate({ to: '/devis/new' })
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      {/* En-tête */}
      <div className="px-6 py-4 border-b border-dark-600 flex items-center justify-between flex-shrink-0">
        <PageHeader title="Builder catalogue" subtitle="Sélectionnez des produits pour composer votre offre" />
        {line_count > 0 && (
          <button
            onClick={clearLines}
            className="text-sm text-dark-500 hover:text-red-400 transition-colors"
          >
            Vider le panier
          </button>
        )}
      </div>

      {/* Corps — 2 colonnes */}
      <div className="flex-1 flex overflow-hidden">
        {/* ————— Colonne gauche : Catalogue ————— */}
        <div className="flex-1 flex flex-col overflow-hidden border-r border-dark-600">
          {/* Filtres */}
          <div className="px-4 py-4 flex gap-2 flex-shrink-0 border-b border-dark-600">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
              <input
                type="text"
                placeholder="Rechercher un produit..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input pl-9 w-full"
              />
            </div>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="input w-44"
            >
              <option value="">Toutes categories</option>
              {categories?.filter((c) => c.parent_id != null).map((cat) => (
                <option key={cat.id} value={cat.slug}>
                  {cat.name}
                </option>
              ))}
            </select>
          </div>

          {/* Liste produits */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {isLoading && (
              <div className="space-y-2 animate-pulse">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-4 p-4 bg-dark-900 rounded-lg">
                    <div className="w-10 h-10 skel rounded-lg shrink-0" />
                    <div className="flex-1 space-y-2">
                      <div className="h-3 skel rounded w-36" />
                      <div className="h-2 skel rounded w-20" />
                    </div>
                    <div className="h-3 skel rounded w-16 shrink-0" />
                  </div>
                ))}
              </div>
            )}
            {!isLoading && queryError && (
              <div className="text-center py-12">
                <p className="text-red-400 mb-4">Erreur lors du chargement du catalogue.</p>
                <button onClick={() => refetch()} className="btn-secondary text-sm">Réessayer</button>
              </div>
            )}
            {!isLoading && !queryError && products.length === 0 && (
              <p className="text-center text-dark-400 py-12 text-sm">
                Aucun produit disponible
              </p>
            )}
            {products.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </div>

        {/* ————— Colonne droite : Panier ————— */}
        <div className="w-96 flex flex-col flex-shrink-0">
          {/* En-tête panier */}
          <div className="px-4 py-4 border-b border-dark-600 flex items-center gap-2 flex-shrink-0">
            <ShoppingCart className="w-4 h-4 text-dark-400" />
            <span className="text-sm font-medium text-dark-300">
              Panier{line_count > 0 ? ` (${line_count} article${line_count > 1 ? 's' : ''})` : ''}
            </span>
          </div>

          {/* Lignes panier */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {line_count === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                <ShoppingCart className="w-10 h-10 text-dark-600 mb-4" />
                <p className="text-sm text-dark-500">Votre panier est vide</p>
                <p className="text-xs text-dark-600 mt-1">
                  Cliquez sur + pour ajouter des produits
                </p>
              </div>
            ) : (
              lines.filter((line) => line.product_id != null).map((line) => (
                <CartLineRow key={line.id} product_id={line.product_id!} />
              ))
            )}
          </div>

          {/* Total + CTAs */}
          {line_count > 0 && (
            <div className="p-4 border-t border-dark-600 space-y-4 flex-shrink-0">
              <div className="flex justify-between items-center">
                <span className="text-sm text-dark-400">Total estimé</span>
                <span className="text-lg font-bold text-dark-100">
                  {(total_cents / 100).toFixed(2)} €
                </span>
              </div>
              <div className="text-xs text-dark-600 -mt-1">
                Hors durée — tarif journalier
              </div>
              <button
                onClick={handleCreateDevis}
                className="btn-primary w-full flex items-center justify-center gap-2"
              >
                <FileText className="w-4 h-4" />
                Créer un devis
              </button>
              <button
                onClick={handleCreateReservation}
                className="btn-secondary w-full"
              >
                Créer une réservation
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
