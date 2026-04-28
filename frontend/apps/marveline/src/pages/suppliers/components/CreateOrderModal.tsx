import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Modal } from '@shared/components/ui/Modal'
import { normalizeError } from '@shared/errors/normalizer'
import { useSupplierOrderMutations } from '@/api/queries/useSupplierOrders'
import { useProductsList } from '@/api/queries/useProducts'
import { supplierOrdersApi } from '@/api/supplier_orders'
import type { SupplierProductPrice } from '@/api/supplier_orders'
import type { SupplierOrderCreate } from '@/types/supplier_order'
import type { Supplier } from '@/types/supplier'

interface LineForm {
  product_id: string
  qty_ordered: string
  unit_cost_euros: string
}

interface CreateOrderModalProps {
  isOpen: boolean
  onClose: () => void
  suppliers: Supplier[]
}

export function CreateOrderModal({ isOpen, onClose, suppliers }: CreateOrderModalProps) {
  const { create } = useSupplierOrderMutations()
  const { data: productsData } = useProductsList({ limit: 500, active_only: true }, isOpen)
  const products = productsData?.items ?? []
  const [form, setForm] = useState({
    supplier_id: '',
    reference: '',
    order_date: '',
    expected_date: '',
    notes: '',
  })
  const [lines, setLines] = useState<LineForm[]>([
    { product_id: '', qty_ordered: '1', unit_cost_euros: '' },
  ])
  const [error, setError] = useState('')
  const [supplierPrices, setSupplierPrices] = useState<SupplierProductPrice[]>([])

  // Charger les prix de reference quand on change de fournisseur
  useEffect(() => {
    if (!form.supplier_id) { setSupplierPrices([]); return }
    supplierOrdersApi.getSupplierPrices(parseInt(form.supplier_id))
      .then(setSupplierPrices)
      .catch(() => setSupplierPrices([]))
  }, [form.supplier_id])

  const findPrice = useCallback((productId: string) => {
    if (!productId) return null
    return supplierPrices.find((p) => p.product_id === parseInt(productId)) ?? null
  }, [supplierPrices])

  const handleClose = () => {
    setForm({ supplier_id: '', reference: '', order_date: '', expected_date: '', notes: '' })
    setLines([{ product_id: '', qty_ordered: '1', unit_cost_euros: '' }])
    setError('')
    onClose()
  }

  const set =
    (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((p) => ({ ...p, [k]: e.target.value }))

  const setLine =
    (i: number, k: keyof LineForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const val = e.target.value
      setLines((prev) => prev.map((l, idx) => {
        if (idx !== i) return l
        const updated = { ...l, [k]: val }
        if (k === 'product_id' && val) {
          const ref = findPrice(val)
          if (ref && (!l.unit_cost_euros || l.unit_cost_euros === '' || l.unit_cost_euros === '0')) {
            updated.unit_cost_euros = (ref.cost_price_cents / 100).toFixed(2)
          }
        }
        return updated
      }))
    }

  const addLine = () =>
    setLines((p) => [...p, { product_id: '', qty_ordered: '1', unit_cost_euros: '' }])

  const removeLine = (i: number) => setLines((p) => p.filter((_, idx) => idx !== i))

  const handleSubmit = async () => {
    setError('')
    if (!form.supplier_id) return setError('Fournisseur requis.')
    if (!form.reference.trim()) return setError('Référence requise.')
    if (lines.some((l) => !l.product_id || parseInt(l.qty_ordered) <= 0))
      return setError('Toutes les lignes doivent avoir un produit et une quantite > 0.')
    if (lines.some((l) => !l.unit_cost_euros || parseFloat(l.unit_cost_euros) <= 0))
      return setError('Veuillez renseigner le prix unitaire HT pour chaque ligne.')

    const payload: SupplierOrderCreate = {
      supplier_id: parseInt(form.supplier_id),
      reference: form.reference.trim(),
      order_date: form.order_date || undefined,
      expected_date: form.expected_date || undefined,
      notes: form.notes.trim() || undefined,
      lines: lines.map((l) => ({
        product_id: parseInt(l.product_id),
        qty_ordered: parseInt(l.qty_ordered),
        unit_cost_cents: Math.round(parseFloat(l.unit_cost_euros) * 100) || 0,
      })),
    }

    try {
      await create.mutateAsync(payload)
      handleClose()
    } catch (err) {
      setError(
        normalizeError(err).message || 'Erreur lors de la création.'
      )
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Nouvelle commande fournisseur"
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={handleClose} className="px-4 py-2 text-sm text-dark-300 hover:text-dark-50">
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={create.isPending}
            className="px-4 py-2 text-sm bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium rounded-lg disabled:opacity-50"
          >
            {create.isPending ? 'Création…' : 'Créer la commande'}
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

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-dark-300 mb-1">Fournisseur *</label>
            <select value={form.supplier_id} onChange={set('supplier_id')} className="input">
              <option value="">— Sélectionner —</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-dark-300 mb-1">Référence *</label>
            <input
              className="input"
              placeholder="CMD-2026-001"
              value={form.reference}
              onChange={set('reference')}
            />
          </div>
          <div>
            <label className="block text-sm text-dark-300 mb-1">Date commande</label>
            <input
              type="date"
              className="input"
              value={form.order_date}
              onChange={set('order_date')}
            />
          </div>
          <div>
            <label className="block text-sm text-dark-300 mb-1">Livraison prévue</label>
            <input
              type="date"
              className="input"
              value={form.expected_date}
              onChange={set('expected_date')}
            />
          </div>
        </div>

        <div>
          <label className="block text-sm text-dark-300 mb-1">Notes</label>
          <textarea
            className="input resize-none"
            rows={2}
            value={form.notes}
            onChange={set('notes')}
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-dark-300">Lignes *</span>
            <button
              type="button"
              onClick={addLine}
              className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300 font-medium"
            >
              <Plus className="w-3.5 h-3.5" />
              Ajouter ligne
            </button>
          </div>
          <div className="flex gap-2 items-center text-xs text-dark-500 mb-1 px-0.5">
            <span className="flex-1">Produit</span>
            <span className="w-20 text-center">Qte</span>
            <span className="w-24 text-center">P.U. HT</span>
            <span className="w-8" />
          </div>
          <div className="space-y-2">
            {lines.map((line, i) => (
              <div key={i} className="flex gap-2 items-center">
                <select
                  className="input flex-1 text-sm"
                  value={line.product_id}
                  onChange={setLine(i, 'product_id')}
                >
                  <option value="">— Produit —</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku})
                    </option>
                  ))}
                </select>
                <input
                  className="input w-20 text-sm"
                  placeholder="Qté"
                  type="number"
                  min="1"
                  value={line.qty_ordered}
                  onChange={setLine(i, 'qty_ordered')}
                />
                <input
                  className="input w-24 text-sm"
                  placeholder="Prix HT €"
                  type="number"
                  min="0"
                  step="0.01"
                  value={line.unit_cost_euros}
                  onChange={setLine(i, 'unit_cost_euros')}
                />
                {lines.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeLine(i)}
                    className="p-1 text-dark-500 hover:text-red-400"
                    aria-label="Supprimer la ligne"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
          <p className="text-xs text-dark-500 mt-1">Produit / Quantité / Prix unitaire HT (€)</p>
        </div>
      </div>
    </Modal>
  )
}
