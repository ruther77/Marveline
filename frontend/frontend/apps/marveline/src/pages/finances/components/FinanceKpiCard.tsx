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
    <div
      className={cn(
        'relative overflow-hidden rounded-2xl border border-dark-700/50',
        'bg-gradient-to-br from-dark-800/80 to-dark-900/90',
        'backdrop-blur-sm shadow-lg shadow-black/10',
        'p-5 flex items-start gap-4 transition-all duration-200',
        'hover:border-dark-600/60 hover:shadow-xl hover:shadow-black/15',
        className,
      )}
    >
      {/* Subtle glow behind icon */}
      <div className="relative">
        <div
          className={cn(
            'absolute inset-0 rounded-xl blur-md opacity-40',
            iconBg,
          )}
        />
        <div
          className={cn(
            'relative flex items-center justify-center shrink-0',
            'rounded-xl border border-white/5',
            iconBg,
            iconColor,
            compact ? 'w-10 h-10' : 'w-12 h-12',
          )}
        >
          {icon}
        </div>
      </div>

      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium text-dark-400 uppercase tracking-wider truncate">
          {title}
        </p>
        <p
          className={cn(
            'font-bold tabular-nums mt-1 tracking-tight',
            compact ? 'text-xl' : 'text-[26px] leading-8',
            valueClass,
          )}
        >
          {value}
        </p>

        {variation != null && (
          <div className="flex items-center gap-1.5 mt-2">
            <div
              className={cn(
                'flex items-center gap-0.5 px-1.5 py-0.5 rounded-md text-[10px] font-semibold',
                isPositive
                  ? 'bg-green-500/15 text-green-400'
                  : 'bg-red-500/15 text-red-400',
              )}
            >
              <TrendIcon className="w-3 h-3" />
              {isPositive ? '+' : ''}{variation.toFixed(1)}%
            </div>
            <span className="text-[10px] text-dark-500">{variationLabel}</span>
          </div>
        )}
      </div>
    </div>
  )
}
