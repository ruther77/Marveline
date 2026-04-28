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
    <div className={cn('card overflow-hidden', className)}>
      <div className="px-5 pt-5 pb-2 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-dark-100">{title}</h3>
          {subtitle && (
            <p className="text-xs text-dark-400 mt-0.5">{subtitle}</p>
          )}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      <div className="px-2 pb-4">{children}</div>
    </div>
  )
}
