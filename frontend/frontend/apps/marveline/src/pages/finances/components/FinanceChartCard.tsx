import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface FinanceChartCardProps {
  title: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}

export function FinanceChartCard({
  title,
  subtitle,
  action,
  children,
  className,
}: FinanceChartCardProps) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-dark-700/50 overflow-hidden',
        'bg-gradient-to-br from-dark-800/80 to-dark-900/90',
        'shadow-lg shadow-black/10',
        className,
      )}
    >
      <div className="px-6 pt-5 pb-1 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-dark-100">{title}</h3>
          {subtitle && (
            <p className="text-[11px] text-dark-500 mt-0.5">{subtitle}</p>
          )}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      <div className="px-3 pb-5 pt-2">{children}</div>
    </div>
  )
}
