import { useState, useCallback, useRef } from 'react'
import { Trash2, Plus, Layers, Package, Minus } from 'lucide-react'
import { formatCents } from '@/lib/utils'
import { CataloguePickerModal } from '@/components/catalogue/CataloguePickerModal'
import type { CataloguePickerLine } from '@/components/catalogue/CataloguePickerModal'
import { CatalogueInlinePicker } from './CatalogueInlinePicker'
// BundlePreviewPanel retire — detail visible dans le catalogue picker
import { VariantSelect } from '@/components/catalogue/VariantSelect'
import { useMediaQuery } from '@/hooks/useMediaQuery'

export interface DevisLineEditorLine {
  product_id?: number
  bundle_id?: number
  variant_id?: number
  label: string
  quantity: number
  unit_price_cents: number
  image_url?: string | null
  short_description?: string | null
}

interface Props {
  lines: DevisLineEditorLine[]
  onChange: (lines: DevisLineEditorLine[]) => void
}

export function DevisLineEditor({ lines, onChange }: Props) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const isDesktop = useMediaQuery('(min-width: 1024px)')
  const linesRef = useRef(lines)
  linesRef.current = lines
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  const handleAdd = useCallback((picked: CataloguePickerLine) => {
    const currentLines = linesRef.current
    const currentOnChange = onChangeRef.current
    const existing = currentLines.findIndex((l) =>
      picked.bundle_id ? l.bundle_id === picked.bundle_id : l.product_id === picked.product_id
    )
    if (existing >= 0) {
      const next = currentLines.map((l, i) =>
        i === existing ? { ...l, quantity: l.quantity + picked.quantity } : l
      )
      currentOnChange(next)
    } else {
      const { product_name, image_url, short_description, ...rest } = picked
      currentOnChange([...currentLines, { ...rest, label: product_name, image_url, short_description }])
    }
  }, [])

  const handleQtyChange = (idx: number, qty: number) => {
    onChange(lines.map((l, i) => (i === idx ? { ...l, quantity: Math.max(1, qty) } : l)))
  }

  const handlePriceChange = (idx: number, euros: string) => {
    const cents = Math.round(parseFloat(euros || '0') * 100)
    onChange(lines.map((l, i) => (i === idx ? { ...l, unit_price_cents: isNaN(cents) ? 0 : cents } : l)))
  }

  const handleVariantChange = useCallback((idx: number, variantId: number | undefined) => {
    onChangeRef.current(
      linesRef.current.map((l, i) => (i === idx ? { ...l, variant_id: variantId } : l))
    )
  }, [])

  const handleRemove = (idx: number) => {
    onChange(lines.filter((_, i) => i !== idx))
  }

  const total = lines.reduce((s, l) => s + l.quantity * l.unit_price_cents, 0)

  const linesList = (
    <div className="space-y-3">
      {lines.length === 0 && (
        <div className="rounded-xl border-2 border-dashed border-dark-600 p-8 text-center">
          <Package className="w-8 h-8 text-dark-500 mx-auto mb-3" />
          <p className="text-sm text-dark-400">
            Aucune ligne — ajoutez des articles {isDesktop ? 'depuis le catalogue' : 'ci-dessous'}.
          </p>
        </div>
      )}

      {lines.map((line, idx) => {
        const isBundle = !!line.bundle_id
        const lineTotal = line.quantity * line.unit_price_cents

        return (
          <div key={idx} className="card rounded-xl overflow-hidden" style={{ padding: 0 }}>
            <div className="p-4 flex items-center gap-4">
              {/* Image ou icone */}
              <div className="w-12 h-12 rounded-lg overflow-hidden shrink-0 bg-dark-950 flex items-center justify-center">
                {line.image_url ? (
                  <img src={line.image_url} alt={line.label} className="w-full h-full object-cover" loading="lazy" />
                ) : isBundle ? (
                  <Layers className="w-5 h-5 text-primary-400" />
                ) : (
                  <Package className="w-5 h-5 text-dark-400" />
                )}
              </div>

              {/* Nom + badge + variante */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold truncate">{line.label}</p>
                  {isBundle && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-primary-500/15 text-primary-400 border border-primary-500/30 shrink-0">
                      Pack
                    </span>
                  )}
                </div>
                <p className="text-xs text-dark-400 mt-0.5">{formatCents(line.unit_price_cents)} / unite</p>
                {isBundle && line.short_description && (
                  <p className="text-[11px] text-dark-500 mt-1 line-clamp-2">{line.short_description}</p>
                )}
                {line.product_id && !isBundle && (
                  <VariantSelect
                    productId={line.product_id}
                    value={line.variant_id}
                    onChange={(vid) => handleVariantChange(idx, vid)}
                  />
                )}
              </div>

              {/* Quantite +/- */}
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={() => handleQtyChange(idx, line.quantity - 1)}
                  className="w-9 h-9 rounded-lg bg-dark-900 hover:bg-dark-700 flex items-center justify-center transition-colors"
                >
                  <Minus className="w-3.5 h-3.5" />
                </button>
                <span className="w-8 text-center text-sm font-bold tabular-nums">{line.quantity}</span>
                <button
                  type="button"
                  onClick={() => handleQtyChange(idx, line.quantity + 1)}
                  className="w-9 h-9 rounded-lg bg-dark-900 hover:bg-dark-700 flex items-center justify-center transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Total ligne */}
              <p className="text-sm font-bold w-20 text-right shrink-0 tabular-nums">{formatCents(lineTotal)}</p>

              {/* Supprimer */}
              <button
                type="button"
                onClick={() => handleRemove(idx)}
                className="text-dark-400 hover:text-red-400 p-1.5 shrink-0 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

          </div>
        )
      })}

      {/* Total */}
      {lines.length > 0 && (
        <div className="flex items-center justify-between px-4 py-3 bg-dark-50/[0.03] border border-dark-600 rounded-xl">
          <span className="text-sm text-dark-400">Total HT</span>
          <span className="text-lg font-bold text-gold-400">{formatCents(total)}</span>
        </div>
      )}

      {/* Mobile : bouton pour ouvrir le modal */}
      {!isDesktop && (
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="w-full flex items-center justify-center gap-2 py-3 text-sm text-gold-400 hover:text-gold-300 font-medium border border-dashed border-dark-600 hover:border-gold-500/40 rounded-xl transition-colors"
        >
          <Plus className="w-4 h-4" />
          Ajouter un article
        </button>
      )}
    </div>
  )

  // Desktop : 2 colonnes (lignes + catalogue inline)
  if (isDesktop) {
    return (
      <div className="grid grid-cols-5 gap-6">
        <div className="col-span-3">{linesList}</div>
        <div className="col-span-2 card p-4 self-start sticky top-20">
          <CatalogueInlinePicker onSelect={handleAdd} />
        </div>
      </div>
    )
  }

  // Mobile : cards + modal
  return (
    <div>
      {linesList}
      <CataloguePickerModal
        isOpen={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={handleAdd}
      />
    </div>
  )
}
