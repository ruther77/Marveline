import { useState, useEffect } from 'react'
import { useParams, Link } from '@tanstack/react-router'
import { Save, Package, AlertCircle } from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import { ActionError } from '@shared/components/ui/ActionError'
import { useProductDetail, useUpdateProduct, useCategoriesList } from '@/api/queries'
import { MoneyInput } from '@shared/components/ui/MoneyInput'
import type { ProductUpdate } from '@/types/product'
import { normalizeError } from '@shared/errors/normalizer'

const PRODUCT_CONDITIONS = [
  { value: 'new', label: 'Neuf' },
  { value: 'excellent', label: 'Excellent état' },
  { value: 'good', label: 'Bon état' },
  { value: 'fair', label: 'État correct' },
]

export default function ProductEditorPage() {
  const { id } = useParams({ strict: false })
  const productId = id ? parseInt(id, 10) : null

  const { data: product, isLoading } = useProductDetail(productId)
  const updateMutation = useUpdateProduct()
  const { data: categories } = useCategoriesList()

  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [pricePerDayCents, setPricePerDayCents] = useState(0)
  const [depositAmountCents, setDepositAmountCents] = useState(0)
  const [stockQuantity, setStockQuantity] = useState(0)
  const [availableQuantity, setAvailableQuantity] = useState(0)
  const [condition, setCondition] = useState('good')
  const [imageUrl, setImageUrl] = useState('')
  const [isActive, setIsActive] = useState(true)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (product) {
      setName(product.name)
      setCategory(product.category)
      setPricePerDayCents(product.price_per_day_cents)
      setDepositAmountCents(product.deposit_amount_cents ?? 0)
      setStockQuantity(product.stock_quantity)
      setAvailableQuantity(product.available_quantity)
      setCondition(product.condition ?? 'good')
      setImageUrl(product.image_url ?? '')
      setIsActive(product.is_active)
    }
  }, [product])

  const handleSave = () => {
    if (!productId || !name.trim()) return
    const data: ProductUpdate = {
      name: name.trim(),
      category,
      price_per_day_cents: pricePerDayCents,
      deposit_amount_cents: depositAmountCents,
      stock_quantity: stockQuantity,
      available_quantity: availableQuantity,
      condition,
      image_url: imageUrl || undefined,
      is_active: isActive,
    }
    updateMutation.mutate(
      { id: productId, data },
      {
        onSuccess: () => {
          setSaved(true)
          setTimeout(() => setSaved(false), 3000)
        },
      }
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="card p-6 space-y-4">
          <div className="h-4 skel rounded w-32" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="h-3 skel rounded w-24" />
                <div className="h-9 skel rounded" />
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (!product) {
    return (
      <div className="text-center py-20">
        <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-4" />
        <p className="text-dark-400">Produit introuvable</p>
        <Link to="/catalogue/products" className="mt-4 btn-secondary inline-block">Retour catalogue</Link>
      </div>
    )
  }

  return (
    <div className="max-w-3xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <BackButton />
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-bold flex items-center gap-2 truncate">
            <Package className="w-6 h-6 text-primary-400 shrink-0" />
            {product.name}
          </h1>
          <p className="text-dark-400 text-sm mt-0.5 font-mono">{product.sku}</p>
        </div>
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="btn-primary flex items-center gap-2 shrink-0"
        >
          <Save className="w-4 h-4" />
          {updateMutation.isPending ? 'Sauvegarde…' : 'Sauvegarder'}
        </button>
      </div>

      <ActionError
        message={updateMutation.error ? (normalizeError(updateMutation.error).message || 'Erreur lors de la sauvegarde') : null}
        onDismiss={() => updateMutation.reset()}
      />

      {saved && (
        <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-xl text-green-400 text-sm">
          Modifications sauvegardées avec succès
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Infos générales */}
        <div className="card p-6 space-y-4 md:col-span-2">
          <h2 className="text-sm font-semibold text-dark-300 uppercase tracking-wide">Informations générales</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-dark-400 mb-1">Nom du produit *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="input"
                placeholder="ex: Table ronde 180cm"
              />
            </div>
            <div>
              <label className="block text-sm text-dark-400 mb-1">SKU</label>
              <input
                type="text"
                value={product.sku}
                disabled
                className="input w-full opacity-50 cursor-not-allowed"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Catégorie *</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="input"
            >
              {(categories ?? []).map((c) => (
                <option key={c.slug} value={c.slug}>{c.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Tarification */}
        <div className="card p-6 space-y-4">
          <h2 className="text-sm font-semibold text-dark-300 uppercase tracking-wide">Tarification</h2>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Prix / jour *</label>
            <MoneyInput
              value={pricePerDayCents}
              onChange={setPricePerDayCents}
              placeholder="0,00"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Caution</label>
            <MoneyInput
              value={depositAmountCents}
              onChange={setDepositAmountCents}
              placeholder="0,00"
            />
          </div>
        </div>

        {/* Stock */}
        <div className="card p-6 space-y-4">
          <h2 className="text-sm font-semibold text-dark-300 uppercase tracking-wide">Stock</h2>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Quantité totale</label>
            <input
              type="number"
              min={0}
              value={stockQuantity}
              onChange={(e) => setStockQuantity(Number(e.target.value))}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Quantité disponible</label>
            <input
              type="number"
              min={0}
              value={availableQuantity}
              onChange={(e) => setAvailableQuantity(Number(e.target.value))}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">État</label>
            <select
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              className="input"
            >
              {PRODUCT_CONDITIONS.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Médias */}
        <div className="card p-6 space-y-4 md:col-span-2">
          <h2 className="text-sm font-semibold text-dark-300 uppercase tracking-wide">Médias</h2>
          <div>
            <label className="block text-sm text-dark-400 mb-1">URL image principale</label>
            <input
              type="url"
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              className="input"
              placeholder="https://…"
            />
          </div>
          {imageUrl && (
            <div className="relative w-32 h-32 rounded-lg overflow-hidden border border-dark-600">
              <img src={imageUrl} alt={name} loading="lazy" className="w-full h-full object-cover" />
            </div>
          )}
        </div>

        {/* Statut */}
        <div className="card p-6 space-y-4 md:col-span-2">
          <h2 className="text-sm font-semibold text-dark-300 uppercase tracking-wide">Statut</h2>
          <label className="flex items-center gap-4 cursor-pointer">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="w-4 h-4 accent-primary-500"
            />
            <span className="text-sm">Produit actif (visible dans le catalogue)</span>
          </label>
          <p className="text-xs text-dark-500">
            Créé le {new Date(product.created_at).toLocaleDateString('fr-FR')} ·
            Modifié le {new Date(product.updated_at).toLocaleDateString('fr-FR')}
          </p>
        </div>
      </div>

      {/* Actions complémentaires */}
      <div className="flex gap-4">
        <Link
          to="/catalogue/products/$id"
          params={{ id: String(productId) }}
          className="btn-secondary flex items-center gap-2 text-sm"
        >
          Historique modifications
        </Link>
        <Link
          to="/catalogue/products/$id/maintenance"
          params={{ id: String(productId) }}
          className="btn-secondary flex items-center gap-2 text-sm"
        >
          Maintenance
        </Link>
      </div>
    </div>
  )
}
