import { PageHeader } from '@/components/PageHeader'
import { useState, useEffect } from 'react'
import { useSearch } from '@tanstack/react-router'
import { normalizeError } from '@shared/errors/normalizer'
import { SlidersHorizontal, Plus } from 'lucide-react'
import { useStockAdjustments, useCreateAdjustment } from '@/api/queries/useStock'
import { useProductsList } from '@/api/queries/useProducts'
import { useDebounce } from '@/hooks/useDebounce'
import { Modal } from '@shared/components/ui/Modal'
import { ComboboxAsync } from '@shared/components/ui/ComboboxAsync'
import type { StockAdjustmentCreate } from '@/types/stock_management'

// ── Formulaire ajustement ────────────────────────────────────────────────────

interface AdjustFormState {
  product_id: number | ''
  delta: string
  reason: string
}

const EMPTY: AdjustFormState = { product_id: '', delta: '', reason: '' }

interface AdjustmentModalProps {
  isOpen: boolean
  onClose: () => void
  initialProductId?: number
}

function AdjustmentModal({ isOpen, onClose, initialProductId }: AdjustmentModalProps) {
  const createAdjustment = useCreateAdjustment()
  const [form, setForm] = useState<AdjustFormState>(() =>
    initialProductId ? { ...EMPTY, product_id: initialProductId } : EMPTY
  )
  const [error, setError] = useState('')
  const [productSearch, setProductSearch] = useState('')
  const debouncedSearch = useDebounce(productSearch, 300)

  const { data: productsData, isLoading: loadingProducts } = useProductsList({
    limit: 20,
    search: debouncedSearch || undefined,
  })
  const products = productsData?.items ?? []

  const handleSubmit = async () => {
    if (!form.product_id) { setError('Sélectionnez un produit.'); return }
    const delta = parseInt(form.delta, 10)
    if (isNaN(delta) || delta === 0) { setError("L'écart doit être un entier non nul."); return }
    if (!form.reason.trim()) { setError('La raison est requise.'); return }

    setError('')
    const payload: StockAdjustmentCreate = {
      product_id: form.product_id as number,
      delta,
      reason: form.reason.trim(),
    }
    try {
      await createAdjustment.mutateAsync(payload)
      setForm(EMPTY)
      setProductSearch('')
      onClose()
    } catch (err) {
      setError(
        normalizeError(err).message || 'Erreur lors de la création.'
      )
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => { setForm(EMPTY); setError(''); setProductSearch(''); onClose() }}
      title="Ajustement manuel"
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={onClose} className="px-4 py-2 text-sm text-dark-300 hover:text-dark-50">
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={createAdjustment.isPending}
            className="px-4 py-2 text-sm bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium rounded-lg disabled:opacity-50"
          >
            {createAdjustment.isPending ? 'Enregistrement…' : 'Créer'}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        {error && (
          <p className="text-red-400 text-sm bg-red-900/20 border border-red-700/30 rounded-lg px-4 py-2">
            {error}
          </p>
        )}

        <div>
          <label className="block text-sm text-dark-300 mb-1">Produit *</label>
          <ComboboxAsync
            value={form.product_id}
            onChange={(id) => setForm((prev) => ({ ...prev, product_id: id }))}
            items={products.map((p) => ({ id: p.id, label: `${p.name} (${p.sku})` }))}
            onSearchChange={setProductSearch}
            isLoading={loadingProducts}
            placeholder="Rechercher un produit…"
          />
        </div>

        <div>
          <label className="block text-sm text-dark-300 mb-1">Écart *</label>
          <input
            type="number"
            value={form.delta}
            onChange={(e) => setForm((prev) => ({ ...prev, delta: e.target.value }))}
            placeholder="Ex: -3 ou +5"
            className="input"
          />
          <p className="text-dark-500 text-xs mt-1">Valeur négative = perte/casse. Positive = ajout.</p>
        </div>

        <div>
          <label className="block text-sm text-dark-300 mb-1">Raison *</label>
          <textarea
            value={form.reason}
            onChange={(e) => setForm((prev) => ({ ...prev, reason: e.target.value }))}
            rows={2}
            placeholder="Ex: Casse lors du transport, correction après inventaire…"
            className="input resize-none"
          />
        </div>
      </div>
    </Modal>
  )
}

// ── Page principale ──────────────────────────────────────────────────────────

export default function StockAdjustmentsPage() {
  const { product_id: presetProductId } = useSearch({ strict: false }) as { product_id?: number }
  const [filterProductId, setFilterProductId] = useState<number | undefined>()
  const [filterSearch, setFilterSearch] = useState('')
  const debouncedFilterSearch = useDebounce(filterSearch, 300)
  const [createOpen, setCreateOpen] = useState(false)

  // Auto-ouvrir la modal si product_id en query param
  useEffect(() => {
    if (presetProductId) setCreateOpen(true)
  }, [presetProductId])

  const { data, isLoading, error: queryError, refetch } = useStockAdjustments(filterProductId)
  const adjustments = data?.items ?? []
  const { data: filterProductsData, isLoading: loadingFilterProducts } = useProductsList({
    limit: 20,
    search: debouncedFilterSearch || undefined,
  })
  const filterProducts = filterProductsData?.items ?? []

  const productName = (id: number) =>
    filterProducts.find((p) => p.id === id)?.name ?? `#${id}`

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <SlidersHorizontal className="w-6 h-6 text-gold-400" />
          <PageHeader title="Ajustements de stock" />
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm px-4 py-2 rounded-lg"
        >
          <Plus className="w-4 h-4" />
          Nouvel ajustement
        </button>
      </div>

      {/* Filtre produit */}
      <div className="flex items-center gap-4 max-w-xs">
        <ComboboxAsync
          value={filterProductId ?? ''}
          onChange={(id) => setFilterProductId(id || undefined)}
          items={filterProducts.map((p) => ({ id: p.id, label: p.name }))}
          onSearchChange={setFilterSearch}
          isLoading={loadingFilterProducts}
          placeholder="Filtrer par produit…"
          className="flex-1"
        />
      </div>

      {/* Liste */}
      {isLoading ? (
        <div className="card divide-y divide-dark-600 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-start justify-between px-4 py-4 gap-4">
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-36" />
                <div className="h-2 skel rounded w-52" />
              </div>
              <div className="h-5 skel rounded w-16 shrink-0" />
            </div>
          ))}
        </div>
      ) : queryError ? (
        <div className="card text-center py-12">
          <p className="text-red-400 mb-4">Erreur lors du chargement des ajustements.</p>
          <button onClick={() => refetch()} className="btn-secondary text-sm">Réessayer</button>
        </div>
      ) : adjustments.length === 0 ? (
        <div className="card text-center py-12">
          <SlidersHorizontal className="w-10 h-10 text-dark-500 mx-auto mb-4" />
          <p className="font-medium">Aucun ajustement</p>
          <p className="text-dark-400 text-sm mt-1">Les ajustements manuels apparaîtront ici.</p>
        </div>
      ) : (
        <div className="card divide-y divide-dark-600">
          {adjustments.map((a) => (
            <div key={a.id} className="flex items-start justify-between px-4 py-4 gap-4">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{productName(a.product_id)}</p>
                <p className="text-dark-400 text-xs mt-0.5 truncate">{a.reason}</p>
                <p className="text-dark-500 text-xs mt-0.5">
                  {new Date(a.created_at).toLocaleString('fr-FR')}
                </p>
              </div>
              <span
                className={`text-sm font-bold shrink-0 ${
                  a.delta > 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {a.delta > 0 ? '+' : ''}
                {a.delta}
              </span>
            </div>
          ))}
        </div>
      )}

      <AdjustmentModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        initialProductId={presetProductId}
      />
    </div>
  )
}
