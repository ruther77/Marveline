import { useState } from 'react'
import { ChevronDown, ChevronRight, Layers, Package, Trash2 } from 'lucide-react'
import { SwipeActions } from '@shared/components/ui/SwipeActions'
import { formatCents } from '@/lib/utils'
import type { ReservationDetail, ReservationLine } from '@/types/reservation'

interface ProductLinesProps {
  reservation: Pick<ReservationDetail, 'id' | 'status' | 'lines' | 'rental_days' | 'total_amount_cents'>
  onNavigateToLines?: () => void
  onRemoveLine?: (lineId: number) => void
}

function SingleProductLine({
  line,
  rental_days,
}: {
  line: ReservationLine
  rental_days: number
}) {
  const imageUrl = line.product?.image_url
  const name = line.variant?.label || line.product?.name || `Article #${line.id}`
  const subName = line.variant && line.product ? line.product.name : undefined
  const sku = line.product?.sku || line.variant?.sku

  return (
    <div className="p-3 card flex gap-3 items-center" style={{ marginBottom: 0 }}>
      <div className="w-14 h-14 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
        {imageUrl ? (
          <img src={imageUrl} alt={name} className="w-full h-full object-cover" loading="lazy" />
        ) : (
          <Package className="w-6 h-6 text-dark-600" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-sm truncate">{name}</div>
        {subName && <div className="text-xs text-dark-400 truncate">{subName}</div>}
        {sku && <div className="text-xs text-dark-500 font-mono mt-0.5">{sku}</div>}
      </div>
      <div className="text-right shrink-0">
        <div className="text-xs text-dark-400">
          {line.quantity} &times; {formatCents(line.unit_price_cents)}/j
          {rental_days > 1 && <span> &times; {rental_days}j</span>}
        </div>
        <div className="font-semibold text-sm text-green-400">
          {formatCents(line.quantity * line.unit_price_cents * Math.max(rental_days, 1))}
        </div>
      </div>
    </div>
  )
}

function BundleLine({
  line,
  rental_days,
}: {
  line: ReservationLine
  rental_days: number
}) {
  const [expanded, setExpanded] = useState(false)
  const bundle = line.bundle
  if (!bundle) return null

  const imageUrl = bundle.image_url
  const items = bundle.items ?? []

  return (
    <div className="card overflow-hidden" style={{ marginBottom: 0 }}>
      {/* Header pack */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full p-3 flex gap-3 items-center text-left hover:bg-dark-700/30 transition-colors"
      >
        <div className="w-14 h-14 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
          {imageUrl ? (
            <img src={imageUrl} alt={bundle.name} className="w-full h-full object-cover" loading="lazy" />
          ) : (
            <Layers className="w-6 h-6 text-primary-400" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm truncate">{bundle.name}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-primary-500/15 text-primary-400 border border-primary-500/30 shrink-0">
              Pack
            </span>
          </div>
          <div className="text-xs text-dark-400 mt-0.5">
            {items.length} article{items.length > 1 ? 's' : ''} &middot; Qté {line.quantity}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="text-right">
            <div className="text-xs text-dark-400">
              {line.quantity} &times; {formatCents(line.unit_price_cents)}/j
              {rental_days > 1 && <span> &times; {rental_days}j</span>}
            </div>
            <div className="font-semibold text-sm text-green-400">
              {formatCents(line.quantity * line.unit_price_cents * Math.max(rental_days, 1))}
            </div>
          </div>
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-dark-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-dark-500" />
          )}
        </div>
      </button>

      {/* Items du pack (accordéon) */}
      {expanded && items.length > 0 && (
        <div className="border-t border-dark-700 bg-dark-800/40">
          {items.map((bi) => (
            <div
              key={bi.id}
              className="px-3 py-2 flex gap-3 items-center border-b border-dark-700/50 last:border-b-0"
            >
              <div className="w-8 h-8 rounded-md overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center ml-4">
                {bi.product.image_url ? (
                  <img src={bi.product.image_url} alt={bi.product.name} className="w-full h-full object-cover" loading="lazy" />
                ) : (
                  <Package className="w-3.5 h-3.5 text-dark-600" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium truncate text-dark-200">{bi.product.name}</div>
                {bi.product.sku && (
                  <div className="text-[10px] text-dark-500 font-mono">{bi.product.sku}</div>
                )}
              </div>
              <div className="text-xs text-dark-400 shrink-0">
                &times; {bi.quantity * line.quantity}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ProductLines({ reservation, onNavigateToLines, onRemoveLine }: ProductLinesProps) {
  const { lines, rental_days, total_amount_cents, status } = reservation
  const isDraft = status === 'draft'

  return (
    <div className="space-y-2">
      {isDraft && onNavigateToLines && (
        <div className="flex justify-end">
          <button onClick={onNavigateToLines} className="text-sm text-primary-400 hover:text-primary-300">
            + Ajouter
          </button>
        </div>
      )}

      {isDraft && lines && lines.length > 0 && (
        <p className="text-xs text-dark-500 mb-2 flex items-center gap-1">
          &larr; Glisse un produit vers la gauche pour le supprimer
        </p>
      )}

      {lines && lines.length > 0 ? (
        <div className="space-y-2">
          {lines.map((line) => {
            const isBundle = !!line.bundle_id && !!line.bundle

            const content = isBundle ? (
              <BundleLine line={line} rental_days={rental_days} />
            ) : (
              <SingleProductLine line={line} rental_days={rental_days} />
            )

            if (isDraft && onRemoveLine) {
              return (
                <SwipeActions
                  key={line.id}
                  className="rounded-xl"
                  actions={[
                    {
                      icon: <Trash2 className="w-4 h-4" />,
                      label: 'Supprimer',
                      color: 'bg-red-500',
                      onClick: () => onRemoveLine(line.id),
                    },
                  ]}
                >
                  {content}
                </SwipeActions>
              )
            }

            return <div key={line.id}>{content}</div>
          })}

          <div className="flex justify-between items-center text-lg font-bold pt-2">
            <span>Total</span>
            <span className="text-green-500">{formatCents(total_amount_cents)}</span>
          </div>
        </div>
      ) : (
        <div className="text-center py-6 border border-dashed border-dark-600 rounded-lg">
          <Package className="w-10 h-10 text-dark-600 mx-auto mb-2" />
          <p className="text-sm text-dark-400">Aucun produit</p>
        </div>
      )}
    </div>
  )
}
