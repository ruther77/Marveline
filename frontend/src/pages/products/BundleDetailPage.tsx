import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { bundlesApi } from '@/api/bundles'
import { productsApi } from '@/api/products'
import type { Product } from '@/types/product'
import {
  ArrowLeft,
  Package,
  Plus,
  Trash2,
  Star,
  Tag,
  Loader2,
  Calculator,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export default function BundleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const bundleId = Number(id)

  const [showAddForm, setShowAddForm] = useState(false)
  const [selectedProductId, setSelectedProductId] = useState<number | ''>('')
  const [quantity, setQuantity] = useState(1)
  const [editingItemId, setEditingItemId] = useState<number | null>(null)
  const [editQuantity, setEditQuantity] = useState(1)

  const { data: bundle, isLoading } = useQuery({
    queryKey: ['bundle', bundleId],
    queryFn: () => bundlesApi.getBundle(bundleId),
    enabled: !!bundleId,
  })

  const { data: productsData } = useQuery({
    queryKey: ['products', 'all'],
    queryFn: () => productsApi.getProducts({ page_size: 200, active_only: true }),
    enabled: showAddForm,
  })

  const { data: priceCalc } = useQuery({
    queryKey: ['bundle-price', bundleId],
    queryFn: () => bundlesApi.calculatePrice(bundleId),
    enabled: !!bundleId && !!bundle?.items?.length,
  })

  const addItemMutation = useMutation({
    mutationFn: ({ productId, qty }: { productId: number; qty: number }) =>
      bundlesApi.addItem(bundleId, { product_id: productId, quantity: qty }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bundle', bundleId] })
      queryClient.invalidateQueries({ queryKey: ['bundle-price', bundleId] })
      setShowAddForm(false)
      setSelectedProductId('')
      setQuantity(1)
    },
  })

  const updateItemMutation = useMutation({
    mutationFn: ({ itemId, qty }: { itemId: number; qty: number }) =>
      bundlesApi.updateItem(bundleId, itemId, { quantity: qty }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bundle', bundleId] })
      queryClient.invalidateQueries({ queryKey: ['bundle-price', bundleId] })
      setEditingItemId(null)
    },
  })

  const removeItemMutation = useMutation({
    mutationFn: (itemId: number) => bundlesApi.removeItem(bundleId, itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bundle', bundleId] })
      queryClient.invalidateQueries({ queryKey: ['bundle-price', bundleId] })
    },
  })

  const handleAddItem = () => {
    if (!selectedProductId || quantity < 1) return
    addItemMutation.mutate({ productId: Number(selectedProductId), qty: quantity })
  }

  const handleUpdateItem = (itemId: number) => {
    if (editQuantity < 1) return
    updateItemMutation.mutate({ itemId, qty: editQuantity })
  }

  // Filter out products already in the bundle
  const availableProducts = (productsData?.items || []).filter(
    (p: Product) => !bundle?.items?.some((item) => item.product_id === p.id)
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    )
  }

  if (!bundle) {
    return (
      <div className="space-y-6">
        <div className="text-center py-16 text-dark-400">
          <Package className="w-12 h-12 mx-auto mb-4 text-dark-600" />
          <p>Formule introuvable</p>
          <button onClick={() => navigate('/products/bundles')} className="btn-primary mt-4">
            Retour aux formules
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/products/bundles" className="p-2 hover:bg-dark-800 rounded-lg">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{bundle.name}</h1>
            {bundle.featured && (
              <Star className="w-5 h-5 text-yellow-500 fill-yellow-500" />
            )}
            <span
              className={cn(
                'inline-flex items-center px-2 py-1 rounded text-xs',
                bundle.is_active
                  ? 'bg-green-500/10 text-green-500'
                  : 'bg-dark-700 text-dark-400'
              )}
            >
              {bundle.is_active ? 'Actif' : 'Inactif'}
            </span>
          </div>
          {bundle.description && (
            <p className="text-dark-400 mt-1">{bundle.description}</p>
          )}
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <label className="text-sm text-dark-400">Prix formule</label>
          <p className="text-xl font-bold mt-1">
            {Number(bundle.bundle_price).toFixed(2)} EUR
          </p>
        </div>
        <div className="card">
          <label className="text-sm text-dark-400">Nettoyage</label>
          <p className="text-xl font-bold mt-1">
            {bundle.cleaning_fee > 0 ? (
              <span className="flex items-center gap-1">
                <Tag className="w-4 h-4 text-blue-500" />
                {Number(bundle.cleaning_fee).toFixed(2)} EUR
              </span>
            ) : (
              <span className="text-dark-500">-</span>
            )}
          </p>
        </div>
        <div className="card">
          <label className="text-sm text-dark-400">Articles</label>
          <p className="text-xl font-bold mt-1">{bundle.total_items || bundle.items.length}</p>
        </div>
        {priceCalc && (
          <div className="card">
            <label className="text-sm text-dark-400 flex items-center gap-1">
              <Calculator className="w-3 h-3" /> Economie
            </label>
            <p className={cn(
              'text-xl font-bold mt-1',
              priceCalc.discount_amount > 0 ? 'text-green-400' : 'text-dark-500'
            )}>
              {priceCalc.discount_amount > 0
                ? `-${Number(priceCalc.discount_amount).toFixed(2)} EUR`
                : '-'}
            </p>
          </div>
        )}
      </div>

      {/* Items table */}
      <div className="card p-0 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-dark-700">
          <h2 className="font-medium">Produits de la formule</h2>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="btn-primary btn-sm flex items-center gap-1"
          >
            <Plus className="w-3 h-3" />
            Ajouter
          </button>
        </div>

        {/* Add item form */}
        {showAddForm && (
          <div className="px-4 py-3 bg-dark-800 border-b border-dark-700">
            {addItemMutation.error && (
              <div className="mb-3 p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
                {(addItemMutation.error as Error).message || 'Erreur'}
              </div>
            )}
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <label className="block text-sm text-dark-400 mb-1">Produit</label>
                <select
                  value={selectedProductId}
                  onChange={(e) => setSelectedProductId(e.target.value ? Number(e.target.value) : '')}
                  className="input w-full"
                >
                  <option value="">Selectionner un produit...</option>
                  {availableProducts.map((p: Product) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku}) — {(p.price_per_day_cents / 100).toFixed(2)} EUR/j
                    </option>
                  ))}
                </select>
              </div>
              <div className="w-24">
                <label className="block text-sm text-dark-400 mb-1">Quantite</label>
                <input
                  type="number"
                  min={1}
                  value={quantity}
                  onChange={(e) => setQuantity(Number(e.target.value))}
                  className="input w-full"
                />
              </div>
              <button
                onClick={handleAddItem}
                disabled={!selectedProductId || addItemMutation.isPending}
                className="btn-primary btn-sm"
              >
                {addItemMutation.isPending ? 'Ajout...' : 'Ajouter'}
              </button>
              <button
                onClick={() => {
                  setShowAddForm(false)
                  setSelectedProductId('')
                  setQuantity(1)
                }}
                className="btn-secondary btn-sm"
              >
                Annuler
              </button>
            </div>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Produit</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">SKU</th>
                <th className="text-center py-3 px-4 text-sm font-medium text-dark-400">Quantite</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">Prix unitaire/j</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {bundle.items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-dark-400">
                    <Package className="w-8 h-8 mx-auto mb-2 text-dark-600" />
                    Aucun produit dans cette formule
                  </td>
                </tr>
              ) : (
                bundle.items.map((item) => (
                  <tr key={item.id} className="border-b border-dark-700 hover:bg-dark-800/50">
                    <td className="py-3 px-4">
                      <span className="font-medium">{item.product.name}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm text-dark-400">{item.product.sku}</span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {editingItemId === item.id ? (
                        <div className="flex items-center justify-center gap-2">
                          <input
                            type="number"
                            min={1}
                            value={editQuantity}
                            onChange={(e) => setEditQuantity(Number(e.target.value))}
                            className="input w-20 text-center"
                          />
                          <button
                            onClick={() => handleUpdateItem(item.id)}
                            disabled={updateItemMutation.isPending}
                            className="btn-primary btn-sm"
                          >
                            OK
                          </button>
                          <button
                            onClick={() => setEditingItemId(null)}
                            className="btn-secondary btn-sm"
                          >
                            X
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setEditingItemId(item.id)
                            setEditQuantity(item.quantity)
                          }}
                          className="px-3 py-1 bg-dark-700 rounded hover:bg-dark-600 transition-colors"
                        >
                          {item.quantity}
                        </button>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className="text-sm">
                        {(item.product.price_per_day_cents / 100).toFixed(2)} EUR
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => removeItemMutation.mutate(item.id)}
                        disabled={removeItemMutation.isPending}
                        className="p-1 hover:bg-red-500/10 rounded text-red-400"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Price summary */}
        {priceCalc && bundle.items.length > 0 && (
          <div className="px-4 py-3 border-t border-dark-700 bg-dark-800/50">
            <div className="flex justify-end gap-8 text-sm">
              <div>
                <span className="text-dark-400">Prix individuel : </span>
                <span>{Number(priceCalc.total_price).toFixed(2)} EUR</span>
              </div>
              {priceCalc.discount_amount > 0 && (
                <div>
                  <span className="text-dark-400">Remise : </span>
                  <span className="text-green-400">-{Number(priceCalc.discount_amount).toFixed(2)} EUR</span>
                </div>
              )}
              <div>
                <span className="text-dark-400">Prix formule : </span>
                <span className="font-bold text-primary-400">{Number(priceCalc.final_price).toFixed(2)} EUR</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
