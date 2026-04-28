import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { ShoppingCart, AlertTriangle, CheckCircle } from 'lucide-react'
import { useReorderList, useCreateReorder } from '@/api/queries/useStock'

type OrderedItem = { product_id: number; product_name: string; quantity: number }

export default function StockReorderPage() {
  const { data: reorderData, isLoading, error: queryError, refetch } = useReorderList()
  const items = reorderData?.items ?? []
  const createReorder = useCreateReorder()

  const [quantities, setQuantities] = useState<Record<number, number>>({})
  const [success, setSuccess] = useState(false)
  const [successOrders, setSuccessOrders] = useState<OrderedItem[]>([])
  const [error, setError] = useState('')

  const setQty = (productId: number, qty: number) =>
    setQuantities((prev) => ({ ...prev, [productId]: qty }))

  const handleOrder = async () => {
    const selected = Object.entries(quantities)
      .filter(([, qty]) => qty > 0)
      .map(([id, qty]) => ({ product_id: Number(id), quantity: qty }))

    if (selected.length === 0) {
      setError('Saisissez au moins une quantité à commander.')
      return
    }

    setError('')
    setSuccess(false)
    try {
      await createReorder.mutateAsync({ items: selected })
      const snap: OrderedItem[] = selected.map(({ product_id, quantity }) => ({
        product_id,
        product_name: items.find((i) => i.product_id === product_id)?.product_name ?? `Produit #${product_id}`,
        quantity,
      }))
      setSuccessOrders(snap)
      setSuccess(true)
      setQuantities({})
    } catch (err) {
      setError(
        normalizeError(err).message || 'Erreur lors de la création du réassort.'
      )
    }
  }

  const totalSelected = Object.values(quantities).filter((q) => q > 0).length

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <ShoppingCart className="w-6 h-6 text-gold-400" />
          <PageHeader title="Réassort" />
          {items.length > 0 && (
            <span className="text-sm text-red-400 flex items-center gap-1">
              <AlertTriangle className="w-4 h-4" />
              {items.length} produit{items.length > 1 ? 's' : ''} sous seuil
            </span>
          )}
        </div>
        {totalSelected > 0 && (
          <button
            onClick={handleOrder}
            disabled={createReorder.isPending}
            className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm px-4 py-2 rounded-lg disabled:opacity-50"
          >
            <ShoppingCart className="w-4 h-4" />
            {createReorder.isPending
              ? 'Création…'
              : `Commander (${totalSelected} produit${totalSelected > 1 ? 's' : ''})`}
          </button>
        )}
      </div>

      {error && (
        <p className="text-red-400 text-sm bg-red-900/20 border border-red-700/30 rounded-lg px-4 py-2">
          {error}
        </p>
      )}

      {success && (
        <div className="card p-0 overflow-hidden bg-green-900/10 border border-green-700/30">
          <div className="flex items-center gap-2 px-4 py-4 border-b border-green-700/20">
            <CheckCircle className="w-4 h-4 text-green-400 shrink-0" />
            <p className="text-sm font-medium text-green-300">Commande de réassort créée avec succès</p>
          </div>
          {successOrders.length > 0 && (
            <div className="divide-y divide-dark-600/50">
              {successOrders.map((o) => (
                <div key={o.product_id} className="flex justify-between px-4 py-2.5 text-sm">
                  <span className="text-dark-300">{o.product_name}</span>
                  <span className="font-medium">× {o.quantity}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {isLoading ? (
        <div className="card divide-y divide-dark-600 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-4">
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-40" />
                <div className="h-2 skel rounded w-56" />
              </div>
              <div className="h-3 skel rounded w-12 shrink-0" />
              <div className="h-3 skel rounded w-12 shrink-0" />
              <div className="h-8 skel rounded w-28 shrink-0" />
            </div>
          ))}
        </div>
      ) : queryError ? (
        <div className="card text-center py-12">
          <p className="text-red-400 mb-4">Erreur lors du chargement des réassorts.</p>
          <button onClick={() => refetch()} className="btn-secondary text-sm">Réessayer</button>
        </div>
      ) : items.length === 0 ? (
        <div className="card text-center py-12">
          <CheckCircle className="w-10 h-10 text-green-500 mx-auto mb-4" />
          <p className="font-medium">Tous les stocks sont suffisants</p>
          <p className="text-dark-400 text-sm mt-1">
            Aucun produit ne dépasse son seuil de réassort.
          </p>
        </div>
      ) : (
        <div className="card divide-y divide-dark-600">
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-4 py-2 text-xs text-dark-400 uppercase tracking-wide">
            <span>Produit</span>
            <span className="text-right">Dispo</span>
            <span className="text-right">Seuil</span>
            <span className="text-right">Qté à cmder</span>
          </div>
          {items.map((item) => (
            <div
              key={item.product_id}
              className="grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center px-4 py-4"
            >
              <div className="min-w-0">
                <p className="text-sm truncate">{item.product_name}</p>
                <p className="text-red-400 text-xs">Déficit : {item.deficit}</p>
              </div>
              <span className="text-red-400 text-sm font-medium text-right">
                {item.available_quantity}
              </span>
              <span className="text-dark-400 text-sm text-right">
                {item.low_stock_threshold}
              </span>
              <input
                type="number"
                min={0}
                value={quantities[item.product_id] ?? ''}
                onChange={(e) => setQty(item.product_id, Number(e.target.value))}
                placeholder={String(item.deficit)}
                className="input w-20 px-2 py-1.5 text-right"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
