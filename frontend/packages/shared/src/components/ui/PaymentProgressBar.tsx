import { cn } from '../../lib/utils'
import { Check } from 'lucide-react'

export interface PaymentProgressBarProps {
  paidCents: number
  totalCents: number
  size?: 'sm' | 'md'
  className?: string
}

function formatEuros(cents: number): string {
  return (cents / 100).toFixed(2).replace('.', ',') + ' €'
}

export function PaymentProgressBar({ paidCents, totalCents, size = 'sm', className }: PaymentProgressBarProps) {
  if (totalCents <= 0) {
    return <span className="text-xs text-dark-500">—</span>
  }

  const percent = Math.min(100, Math.round((paidCents / totalCents) * 100))
  const isPaid = paidCents >= totalCents

  const barH = size === 'sm' ? 'h-1.5' : 'h-2'
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm'

  if (isPaid) {
    return (
      <div className={cn('flex items-center gap-1', textSize, className)}>
        <Check className="w-3.5 h-3.5 text-green-400" />
        <span className="text-green-400 font-medium">Payé</span>
      </div>
    )
  }

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div className={cn('w-full rounded-full bg-dark-900 overflow-hidden', barH)}>
        <div
          className={cn(
            'h-full rounded-full transition-all',
            paidCents > 0 ? 'bg-green-500' : 'bg-dark-600',
          )}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className={cn(textSize, 'text-dark-400')}>
        {formatEuros(paidCents)} / {formatEuros(totalCents)}
      </span>
    </div>
  )
}
