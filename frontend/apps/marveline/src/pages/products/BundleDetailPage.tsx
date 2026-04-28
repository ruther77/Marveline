import { useState } from 'react'
import { useParams, useNavigate } from '@tanstack/react-router'
import {
  useBundleDetail,
  useBundlePrice,
  useProductsList,
  useAddBundleItem,
  useUpdateBundleItem,
  useRemoveBundleItem,
} from '@/api/queries'
import type { Product } from '@/types/product'
import { ActionError } from '@shared/components/ui/ActionError'
import { ErrorState } from '@shared/components/ui/EmptyState'
import {
  Package,
  Plus,
  Trash2,
  Star,
  Tag,
  Loader2,
  Calculator,
} from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import { cn, formatCents } from '@/lib/utils'
import { PAGE_SIZE_SELECT } from '@/lib/constants'
import { normalizeError } from '@shared/errors/normalizer'

export default function BundleDetailPage() {
  const { id } = useParams({ strict: false })
  const navigate = useNavigate()
  const bundleId = Number(id)

  const [showAddForm, setShowAddForm] = useState(false)
  const [selectedProductId, setSelectedProductId] = useState<number | ''>('')
  const [quantity, setQuantity] = useState(1)
  const [editingItemId, setEditingItemId] = useState<number | null>(null)
  const [editQuantity, setEditQuantity] = useState(1)

  const { data: bundle, isLoading, error, refetch } = useBundleDetail(bundleId || null)
  const { data: productsData } = useProductsList({ limit: PAGE_SIZE_SELECT, active_only: true })
  const { data: priceCalc } = useBundlePrice(bundleId || null)

  const addItemMutation = useAddBundleItem()
  const updateItemMutation = useUpdateBundleItem()
  const removeItemMutation = useRemoveBundleItem()

  const handleAddItem = () => {
    if (!selectedProductId || quantity < 1) return
    addItemMutation.mutate(
      { bundleId, item: { product_id: Number(selectedProductId), quantity } },
      {
        onSuccess: () => {
          setShowAddForm(false)
          setSelectedProductId('')
          setQuantity(1)
        },
      }
    )
  }

  const handleUpdateItem = (itemId: number) => {
    if (editQuantity < 1) return
    updateItemMutation.mutate(
      { bundleId, itemId, quantity: editQuantity },
      { onSuccess: () => setEditingItemId(null) }
    )
  }

  // Filter out products already in the bundle
  const availableProducts = (productsData?.items || []).filter(
    (p: Product) => !bundle?.items?.some((item) => item.product_id === p.id)
  )

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="card p-6 space-y-4">
          <div className="h-5 skel rounded w-48" />
          <div className="h-3 skel rounded w-64" />
        </div>
        <div className="card divide-y divide-dark-600">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-4">
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-36" />
                <div className="h-2 skel rounded w-24" />
              </div>
              <div className="h-3 skel rounded w-16 shrink-0" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error) return <ErrorState onRetry={() => refetch()} />

  if (!bundle) {
    return (
      <div className="space-y-6">
        <div className="text-center py-16 text-dark-400">
          <Package className="w-12 h-12 mx-auto mb-4 text-dark-600" />
          <p>Formule introuvable</p>
          <button onClick={() => navigate({ to: '/catalogue/bundles' })} className="btn-primary mt-4">
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
        <BackButton />
        {bundle.image_url ? (
          <img src={bundle.image_url} alt={bundle.name} className="w-16 h-16 rounded-xl object-cover shrink-0" />
        ) : (
          <div className="w-16 h-16 rounded-xl bg-dark-950 flex items-center justify-center shrink-0">
            <Package className="w-6 h-6 text-dark-600" />
          </div>
        )}
        <div className="flex-1">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold">{bundle.name}</h1>
            {bundle.featured && (
              <Star className="w-5 h-5 text-yellow-500 fill-yellow-500" />
            )}
            <span
              className={cn(
                'inline-flex items-center px-2 py-1 rounded text-xs',
                bundle.is_active
                  ? 'bg-green-500/10 text-green-500'
                  : 'bg-dark-900 text-dark-400'
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
            {(bundle.bundle_price_euros ?? 0).toFixed(2)} EUR
          </p>
        </div>
        <div className="card">
          <label className="text-sm text-dark-400">Nettoyage</label>
          <p className="text-xl font-bold mt-1">
            {bundle.cleaning_fee_cents > 0 ? (
              <span className="flex items-center gap-1">
                <Tag className="w-4 h-4 text-blue-500" />
                {(bundle.cleaning_fee_euros ?? 0).toFixed(2)} EUR
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
              (priceCalc.savings_cents ?? 0) > 0 ? 'text-green-400' : 'text-dark-500'
            )}>
              {(priceCalc.savings_cents ?? 0) > 0
                ? `-${formatCents(priceCalc.savings_cents ?? 0)}`
                : '-'}
            </p>
          </div>
        )}
      </div>

      {/* Items table */}
      <div className="card p-0 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-4 border-b border-dark-600">
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
          <div className="px-4 py-4 bg-dark-900 border-b border-dark-600">
            <ActionError
              message={addItemMutation.error ? (normalizeError(addItemMutation.error).message || 'Erreur') : null}
              onDismiss={() => addItemMutation.reset()}
            />
            <div className="flex gap-4 items-end">
              <div className="flex-1">
                <label className="block text-sm text-dark-400 mb-1">Produit</label>
                <select
                  value={selectedProductId}
                  onChange={(e) => setSelectedProductId(e.target.value ? Number(e.target.value) : '')}
                  className="input"
                >
                  <option value="">Selectionner un produit...</option>
                  {availableProducts.map((p: Product) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku}) — {formatCents(p.price_per_day_cents ?? 0)}/j
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
                  className="input"
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
              <tr className="border-b border-dark-600">
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">Produit</th>
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">SKU</th>
                <th className="text-center py-4 px-4 text-sm font-medium text-dark-400">Quantite</th>
                <th className="text-right py-4 px-4 text-sm font-medium text-dark-400">Prix unitaire/j</th>
                <th className="text-right py-4 px-4 text-sm font-medium text-dark-400">Actions</th>
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
                  <tr key={item.id} className="border-b border-dark-600 hover:bg-dark-900/50">
                    <td className="py-4 px-4">
                      <span className="font-medium">{item.product.name}</span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="font-mono text-sm text-dark-400">{item.product.sku}</span>
                    </td>
                    <td className="py-4 px-4 text-center">
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
                          className="px-4 py-1 bg-dark-900 rounded hover:bg-dark-600 transition-colors"
                        >
                          {item.quantity}
                        </button>
                      )}
                    </td>
                    <td className="py-4 px-4 text-right">
                      <span className="text-sm">
                        {formatCents(item.product.price_per_day_cents ?? 0)}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <button
                        onClick={() => removeItemMutation.mutate({ bundleId, itemId: item.id })}
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
          <div className="px-4 py-4 border-t border-dark-600 bg-dark-900/50">
            <div className="flex justify-end gap-8 text-sm">
              <div>
                <span className="text-dark-400">Prix individuel : </span>
                <span>{formatCents(priceCalc.individual_price_cents ?? 0)}</span>
              </div>
              {(priceCalc.savings_cents ?? 0) > 0 && (
                <div>
                  <span className="text-dark-400">Remise : </span>
                  <span className="text-green-400">-{formatCents(priceCalc.savings_cents ?? 0)}</span>
                </div>
              )}
              <div>
                <span className="text-dark-400">Prix formule : </span>
                <span className="font-bold text-primary-400">{formatCents(priceCalc.bundle_price_cents ?? 0)}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
