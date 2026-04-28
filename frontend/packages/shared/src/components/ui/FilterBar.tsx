import { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export interface FilterChip {
  key: string
  label: string
  value: string
  onRemove: () => void
}

export interface FilterBarProps {
  chips?: FilterChip[]
  children?: ReactNode
  onClearAll?: () => void
  className?: string
}

export function FilterBar({ chips = [], children, onClearAll, className }: FilterBarProps) {
  const hasActive = chips.length > 0

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      {children}
      {chips.map((chip) => (
        <span
          key={chip.key}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary-700/30 border border-primary-600/50 text-xs text-primary-300"
        >
          <span className="text-dark-400">{chip.label}:</span>
          {chip.value}
          <button
            type="button"
            className="ml-0.5 text-dark-400 hover:text-dark-50 transition-colors"
            onClick={chip.onRemove}
            aria-label={`Supprimer filtre ${chip.label}`}
          >
            ×
          </button>
        </span>
      ))}
      {hasActive && onClearAll && (
        <button
          type="button"
          onClick={onClearAll}
          className="text-xs text-dark-400 hover:text-dark-50 transition-colors underline-offset-2 hover:underline"
        >
          Effacer tout
        </button>
      )}
    </div>
  )
}
