import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export interface KanbanColumn<T> {
  key: string
  label: string
  color: string
  items: T[]
}

export interface KanbanBoardProps<T> {
  columns: KanbanColumn<T>[]
  renderCard: (item: T) => ReactNode
  onCardClick?: (item: T) => void
  className?: string
  emptyLabel?: string
}

export function KanbanBoard<T>({
  columns,
  renderCard,
  onCardClick,
  className,
  emptyLabel = 'Aucun élément',
}: KanbanBoardProps<T>) {
  return (
    <div
      className={cn(
        'flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory',
        'scrollbar-thin scrollbar-track-dark-900 scrollbar-thumb-dark-600',
        className,
      )}
    >
      {columns.map((col) => (
        <div
          key={col.key}
          className="flex-shrink-0 w-72 sm:w-80 snap-start flex flex-col"
        >
          {/* Column header */}
          <div className="flex items-center gap-2 mb-3 px-1">
            <div className={cn('w-2 h-2 rounded-full', col.color)} />
            <h3 className="text-sm font-semibold text-dark-200">{col.label}</h3>
            <span className="text-xs text-dark-500 bg-dark-900 px-1.5 py-0.5 rounded-full">
              {col.items.length}
            </span>
          </div>

          {/* Cards */}
          <div className="flex-1 space-y-2 overflow-y-auto max-h-[60vh] pr-1">
            {col.items.length === 0 ? (
              <div className="text-xs text-dark-500 text-center py-8 bg-dark-900/50 rounded-xl border border-dashed border-dark-600">
                {emptyLabel}
              </div>
            ) : (
              col.items.map((item, i) => (
                <div
                  key={i}
                  className={cn(
                    'card p-3',
                    'hover:border-dark-500 transition-colors',
                    onCardClick && 'cursor-pointer',
                  )}
                  onClick={() => onCardClick?.(item)}
                >
                  {renderCard(item)}
                </div>
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
