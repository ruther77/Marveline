import type { ReactNode } from 'react'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface FinanceKpiCardProps {
  title: string
  value: string | number
  icon: ReactNode
  iconBg?: string
  iconColor?: string
  variation?: number | null
  variationLabel?: string
  valueClass?: string
  compact?: boolean
  className?: string
}

export function FinanceKpiCard({
  title,
  value,
  icon,
  iconBg = 'bg-primary-500/10',
  iconColor = 'text-primary-400',
  variation,
  variationLabel = 'vs N-1',
  valueClass = 'text-dark-50',
  compact = false,
  className,
}: FinanceKpiCardProps) {
  const isPositive = variation != null && variation >= 0
  const TrendIcon = isPositive ? TrendingUp : TrendingDown

  return (
    <div className={cn('card p-5 flex items-start gap-4', className)}>
      <div
        className={cn(
          'flex items-center justify-center shrink-0',
          iconBg,
          iconColor,
          compact ? 'w-9 h-9 rounded-lg' : 'w-11 h-11 rounded-xl',
        )}
      >
        {icon}
      </div>

      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-dark-400 truncate">{title}</p>
        <p
          className={cn(
            'font-bold tabular-nums mt-0.5',
            compact ? 'text-xl' : 'text-2xl',
            valueClass,
          )}
        >
          {value}
        </p>

        {variation != null && (
          <div className="flex items-center gap-1 mt-1">
            <TrendIcon className={cn('w-3.5 h-3.5', isPositive ? 'text-green-400' : 'text-red-400')} />
            <span
              className={cn(
                'text-xs font-medium',
                isPositive ? 'text-green-400' : 'text-red-400',
              )}
            >
              {isPositive ? '+' : ''}
              {variation.toFixed(1)}%
            </span>
            <span className="text-xs text-dark-500">{variationLabel}</span>
          </div>
        )}
      </div>
    </div>
  )
}
