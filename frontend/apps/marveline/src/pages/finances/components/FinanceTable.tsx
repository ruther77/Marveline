import type { ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Column<T> {
  key: string
  label: string
  align?: 'left' | 'right' | 'center'
  className?: string
  render?: (row: T) => ReactNode
}

interface FinanceTableProps<T> {
  title: string
  columns: Column<T>[]
  data: T[]
  keyExtractor: (row: T) => string | number
  onRowClick?: (row: T) => void
  emptyMessage?: string
  maxRows?: number
  viewAllHref?: string
  className?: string
  footer?: ReactNode
}

export function FinanceTable<T>({
  title,
  columns,
  data,
  keyExtractor,
  onRowClick,
  emptyMessage = 'Aucune donnée',
  maxRows,
  viewAllHref,
  className,
  footer,
}: FinanceTableProps<T>) {
  const rows = maxRows ? data.slice(0, maxRows) : data

  return (
    <div className={cn('card overflow-hidden', className)}>
      <div className="px-5 py-3.5 border-b border-dark-700 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-dark-100">{title}</h3>
        {viewAllHref && (
          <Link
            to={viewAllHref}
            className="text-xs text-primary-400 hover:text-primary-300 flex items-center gap-0.5"
          >
            Voir tout
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-dark-700/50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    'px-4 py-2.5 text-xs font-medium text-dark-400 whitespace-nowrap',
                    col.align === 'right' && 'text-right',
                    col.align === 'center' && 'text-center',
                    col.className,
                  )}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-700/30">
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-8 text-center text-dark-400 text-sm"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr
                  key={keyExtractor(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cn(
                    'transition-colors',
                    onRowClick
                      ? 'cursor-pointer hover:bg-dark-800/50'
                      : 'hover:bg-dark-800/30',
                  )}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={cn(
                        'px-4 py-3 whitespace-nowrap',
                        col.align === 'right' && 'text-right',
                        col.align === 'center' && 'text-center',
                        col.className,
                      )}
                    >
                      {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {footer && (
        <div className="px-4 py-3 border-t border-dark-700">{footer}</div>
      )}
    </div>
  )
}
