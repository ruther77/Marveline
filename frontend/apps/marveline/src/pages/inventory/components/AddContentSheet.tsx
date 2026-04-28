import { useState, useMemo } from 'react'
import { Search, Package, Plus } from 'lucide-react'
import { BottomSheet } from '@shared/components/ui/BottomSheet'
import { ModalFooter } from '@shared/components/ui/Modal'
import { normalizeError } from '@shared/errors/normalizer'
import { useProductsList } from '@/api/queries'
import { useAddContainerContent } from '@/api/queries/useContainers'
import { useDebounce } from '@/hooks/useDebounce'
import type { Product } from '@/types/product'

interface Props {
  isOpen: boolean
  onClose: () => void
  containerId: number
}

export default function AddContentSheet({ isOpen, onClose, containerId }: Props) {
  const [search, setSearch] = useState('')
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [selectedVariantId, setSelectedVariantId] = useState<number | null>(null)
  const [quantity, setQuantity] = useState('1')
  const debouncedSearch = useDebounce(search, 250)

  const { data: productsData } = useProductsList(
    { search: debouncedSearch || undefined, limit: 30 },
    isOpen
  )
  const addMut = useAddContainerContent()

  const products = useMemo(() => {
    return productsData?.items ?? []
  }, [productsData])

  const handleSelectProduct = (p: Product) => {
    setSelectedProduct(p)
    setSelectedVariantId(null)
    setQuantity('1')
  }

  const handleSubmit = () => {
    if (!selectedProduct) return
    const qty = Number(quantity)
    if (qty <= 0) return

    addMut.mutate(
      {
        containerId,
        data: {
          product_id: selectedProduct.id,
          variant_id: selectedVariantId || null,
          quantity: qty,
        },
      },
      {
        onSuccess: () => {
          setSelectedProduct(null)
          setSelectedVariantId(null)
          setQuantity('1')
          setSearch('')
          onClose()
        },
      }
    )
  }

  const handleClose = () => {
    setSelectedProduct(null)
    setSearch('')
    setQuantity('1')
    onClose()
  }

  return (
    <BottomSheet
      isOpen={isOpen}
      onClose={handleClose}
      title="Ajouter un produit"
      size="lg"
      footer={
        selectedProduct ? (
          <ModalFooter
            onCancel={handleClose}
            onConfirm={handleSubmit}
            confirmText="Ajouter"
            loading={addMut.isPending}
            disabled={Number(quantity) <= 0}
          />
        ) : undefined
      }
    >
      <div className="space-y-4">
        {addMut.error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-[var(--red)] text-sm">
            {normalizeError(addMut.error).message || 'Une erreur est survenue'}
          </div>
        )}

        {!selectedProduct ? (
          <>
            {/* Search */}
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
              <input
                className="input pl-9 w-full"
                placeholder="Rechercher un produit..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                autoFocus
              />
            </div>

            {/* Product list */}
            <div className="space-y-1 max-h-[50vh] overflow-y-auto">
              {products.length === 0 ? (
                <p className="text-sm text-[var(--muted)] text-center py-6">
                  {debouncedSearch ? 'Aucun produit trouve' : 'Tapez pour rechercher'}
                </p>
              ) : (
                products.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => handleSelectProduct(p)}
                    className="w-full text-left p-3 rounded-xl hover:bg-[var(--s2)] transition-colors flex items-center gap-3"
                  >
                    {p.image_url ? (
                      <img src={p.image_url} alt="" className="w-10 h-10 rounded-lg object-cover shrink-0" />
                    ) : (
                      <div className="w-10 h-10 rounded-lg bg-[var(--s2)] flex items-center justify-center shrink-0">
                        <Package size={18} className="text-[var(--muted)]" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[var(--text)] truncate">{p.name}</p>
                      <p className="text-xs text-[var(--muted)]">{p.sku} · Stock: {p.stock_quantity}</p>
                    </div>
                    <Plus size={16} className="text-[var(--muted)] shrink-0" />
                  </button>
                ))
              )}
            </div>
          </>
        ) : (
          <>
            {/* Selected product */}
            <div className="card-inner p-3 flex items-center gap-3">
              {selectedProduct.image_url ? (
                <img src={selectedProduct.image_url} alt="" className="w-10 h-10 rounded-lg object-cover" />
              ) : (
                <div className="w-10 h-10 rounded-lg bg-[var(--pink)]/10 flex items-center justify-center">
                  <Package size={18} className="text-[var(--pink)]" />
                </div>
              )}
              <div className="flex-1">
                <p className="text-sm font-medium text-[var(--text)]">{selectedProduct.name}</p>
                <p className="text-xs text-[var(--muted)]">{selectedProduct.sku}</p>
              </div>
              <button
                onClick={() => setSelectedProduct(null)}
                className="text-xs text-[var(--pink)] font-medium"
              >
                Changer
              </button>
            </div>

            {/* Quantity */}
            <div>
              <label className="block text-sm text-[var(--muted)] mb-1">Quantite</label>
              <input
                className="input w-full"
                type="number"
                min="1"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
              />
            </div>
          </>
        )}
      </div>
    </BottomSheet>
  )
}
