import { useState } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { BottomSheet } from '@shared/components/ui/BottomSheet'
import { useUpdateStockItemStatus } from '@/api/queries/useStock'
import { cn } from '@/lib/utils'

type StockStatus = 'available' | 'reserved' | 'on_location' | 'damaged' | 'in_repair' | 'retired'

const STATUS_OPTIONS: { value: StockStatus; label: string; dot: string; bg: string; color: string }[] = [
  { value: 'available',   label: 'Disponible',    dot: 'bg-green-400',  bg: 'bg-green-500/10 border-green-500/30',   color: 'text-green-400' },
  { value: 'reserved',    label: 'Réservé',        dot: 'bg-blue-400',   bg: 'bg-blue-500/10 border-blue-500/30',     color: 'text-blue-400' },
  { value: 'on_location', label: 'En location',    dot: 'bg-orange-400', bg: 'bg-orange-500/10 border-orange-500/30', color: 'text-orange-400' },
  { value: 'damaged',     label: 'Endommagé',      dot: 'bg-red-400',    bg: 'bg-red-500/10 border-red-500/30',       color: 'text-red-400' },
  { value: 'in_repair',   label: 'En réparation',  dot: 'bg-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/30', color: 'text-yellow-400' },
  { value: 'retired',     label: 'Retiré',         dot: 'bg-dark-400',   bg: 'bg-dark-900 border-dark-600',           color: 'text-dark-400' },
]

const NOTE_STATUSES: StockStatus[] = ['damaged', 'in_repair']

interface StockItemStatusSheetProps {
  isOpen: boolean
  onClose: () => void
  productId: number
  itemId: number
  currentStatus: StockStatus
  itemLabel?: string
}

export function StockItemStatusSheet({
  isOpen,
  onClose,
  productId,
  itemId,
  currentStatus,
  itemLabel,
}: StockItemStatusSheetProps) {
  const updateStatus = useUpdateStockItemStatus(productId)
  const [selected, setSelected] = useState<StockStatus>(currentStatus)
  const [note, setNote] = useState('')
  const [isPending, setIsPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit() {
    if (updateStatus.isPending) return
    setIsPending(true)
    setError(null)
    try {
      await updateStatus.mutateAsync({ itemId, status: selected })
      onClose()
    } catch (err) {
      setError(
        normalizeError(err).message || 'Erreur lors de la mise à jour',
      )
    } finally {
      setIsPending(false)
    }
  }

  return (
    <BottomSheet isOpen={isOpen} onClose={onClose} title={itemLabel ? `Statut — ${itemLabel}` : 'Changer le statut'}>
      <div className="space-y-4 pb-2">
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Options statut */}
        <div className="space-y-2">
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setSelected(opt.value)}
              className={cn(
                'w-full flex items-center gap-4 px-4 py-4 rounded-xl border transition-colors text-left',
                selected === opt.value ? `${opt.bg} ${opt.color}` : 'bg-dark-900 border-dark-600 hover:bg-dark-600',
              )}
            >
              <span className={cn('w-2.5 h-2.5 rounded-full shrink-0', opt.dot)} />
              <span className="text-sm font-medium">{opt.label}</span>
              {selected === opt.value && (
                <span className="ml-auto text-xs opacity-70">✓</span>
              )}
            </button>
          ))}
        </div>

        {/* Note optionnelle */}
        {NOTE_STATUSES.includes(selected) && (
          <div>
            <label className="block text-sm text-dark-400 mb-1">Note (optionnelle)</label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value.slice(0, 200))}
              rows={3}
              className="input resize-none"
              placeholder="Décrire l'état ou l'intervention…"
            />
            <p className="text-xs text-dark-500 mt-1 text-right">{note.length}/200</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-4">
          <button onClick={onClose} className="btn-secondary flex-1">
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={isPending || selected === currentStatus}
            className="btn-primary flex-1 disabled:opacity-50"
          >
            {isPending ? 'Mise à jour…' : 'Valider'}
          </button>
        </div>
      </div>
    </BottomSheet>
  )
}
