import { cn } from '../../lib/utils'

export interface StockIndicatorProps {
  current: number
  min: number
  max?: number
  unit?: string
  className?: string
}

export function StockIndicator({
  current,
  min,
  max,
  unit,
  className,
}: StockIndicatorProps) {
  const pct = max && max > 0 ? Math.round((current / max) * 100) : 100

  const { color, label } = (() => {
    if (current <= min) return { color: 'bg-red-500', label: 'Rupture' }
    if (current <= min * 2) return { color: 'bg-orange-400', label: 'Faible' }
    return { color: 'bg-green-500', label: 'OK' }
  })()

  return (
    <div className={cn('flex items-center gap-2', className)}>
      {max != null && (
        <div className="flex-1 h-1.5 rounded-full bg-dark-900 overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all', color)}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
      <span className="text-xs text-dark-300 shrink-0">
        {current}{unit ? ` ${unit}` : ''} — {label}
      </span>
    </div>
  )
}
