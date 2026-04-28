import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export interface DaySummaryItem {
  label: string
  value: string | number
  icon?: ReactNode
  color?: string
}

export interface DaySummaryBarProps {
  items: DaySummaryItem[]
  className?: string
}

function SummaryCell({ item }: { item: DaySummaryItem }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2.5">
      {item.icon && (
        <span
          className={cn('shrink-0 w-7 h-7 flex items-center justify-center rounded-lg bg-dark-900', item.color)}
          aria-hidden="true"
        >
          {item.icon}
        </span>
      )}
      <div className="min-w-0">
        <p className="text-xs text-dark-400 truncate leading-none mb-0.5">{item.label}</p>
        <p className={cn('text-sm font-bold leading-none truncate', item.color ?? 'text-dark-50')}>
          {item.value}
        </p>
      </div>
    </div>
  )
}

export function DaySummaryBar({ items, className }: DaySummaryBarProps) {
  if (items.length === 0) return null

  return (
    <div
      className={cn(
        'card overflow-hidden',
        'grid grid-cols-2 sm:grid-cols-4',
        className,
      )}
    >
      {items.map((item, i) => (
        <div
          key={i}
          className={cn(
            i < items.length - 1 && 'border-r border-dark-600 sm:border-r',
            i < items.length - 2 && 'border-b border-dark-600 sm:border-b-0',
          )}
        >
          <SummaryCell item={item} />
        </div>
      ))}
    </div>
  )
}
