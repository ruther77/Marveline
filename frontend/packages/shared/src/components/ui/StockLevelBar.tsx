import { cn } from '../../lib/utils'

export interface StockLevelBarProps {
  available: number
  total: number
  size?: 'sm' | 'md'
  className?: string
}

export function StockLevelBar({ available, total, size = 'sm', className }: StockLevelBarProps) {
  if (total <= 0) {
    return <span className="text-xs text-dark-500">—</span>
  }

  const percent = Math.round((available / total) * 100)
  const barColor =
    percent === 0 ? 'bg-red-500' :
    percent <= 20 ? 'bg-amber-500' :
    'bg-green-500'

  const barH = size === 'sm' ? 'h-1.5' : 'h-2'
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm'

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div className={cn('w-full rounded-full bg-dark-900 overflow-hidden', barH)}>
        <div
          className={cn('h-full rounded-full transition-all', barColor)}
          style={{ width: `${Math.max(percent, 2)}%` }}
        />
      </div>
      <span className={cn(textSize, 'text-dark-400')}>
        {available} / {total} dispo
      </span>
    </div>
  )
}
