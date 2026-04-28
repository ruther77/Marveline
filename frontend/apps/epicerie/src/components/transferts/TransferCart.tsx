import { Trash2 } from 'lucide-react'
import { formatCents } from '@/utils/etl-helpers'
import { DEFAULT_TRANSFER_TVA_PCT, getTransferTtcCts } from '@/utils/transferts'
import TransferSummary from './TransferSummary'

export interface TransferCartLine {
  productId: number
  designation: string
  availableQty: number
  quantity: number
  unitPriceCts: number
  unitLabel?: string
}

interface TransferCartProps {
  lines: TransferCartLine[]
  onQuantityChange: (productId: number, quantity: number) => void
  onRemove: (productId: number) => void
  tvaPct?: number
}

export default function TransferCart({
  lines,
  onQuantityChange,
  onRemove,
  tvaPct = DEFAULT_TRANSFER_TVA_PCT,
}: TransferCartProps) {
  const totalHtCts = lines.reduce((sum, line) => sum + Math.round(line.unitPriceCts * line.quantity), 0)
  const totalTtcCts = getTransferTtcCts(totalHtCts, tvaPct)

  if (lines.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
        <p className="text-sm text-slate-400">Recherchez et ajoutez des produits au panier.</p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
        <span className="text-sm font-semibold text-slate-700">
          Panier ({lines.length} article{lines.length > 1 ? 's' : ''})
        </span>
      </div>

      <div className="divide-y divide-slate-100">
        {lines.map(line => {
          const overStock = line.quantity > line.availableQty

          return (
            <div key={line.productId} className="flex min-h-11 items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-800">{line.designation}</p>
                <p className="text-xs text-slate-400">
                  stock: {line.availableQty} · {formatCents(line.unitPriceCts)} HT/{line.unitLabel || 'u'}
                </p>
              </div>

              <input
                type="number"
                min={1}
                max={line.availableQty}
                value={line.quantity}
                onChange={event => onQuantityChange(line.productId, Number(event.target.value) || 0)}
                className={`h-11 w-16 rounded-lg border px-2 text-center text-sm ${
                  overStock ? 'border-red-400 bg-red-50 text-red-600' : 'border-slate-300 text-slate-700'
                }`}
              />

              <span className="w-24 text-right font-mono text-sm text-slate-700">
                {formatCents(Math.round(line.unitPriceCts * line.quantity))}
              </span>

              <button
                type="button"
                onClick={() => onRemove(line.productId)}
                className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500"
                aria-label={`Retirer ${line.designation}`}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          )
        })}
      </div>

      <TransferSummary totalHtCts={totalHtCts} totalTtcCts={totalTtcCts} tvaPct={tvaPct} />
    </div>
  )
}
