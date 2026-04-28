import type { ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Column<T> {
  key: string
  label: string
  align?: 'left' | 'right' | 'center'
  className?: string
  render?: (row: T, index: number) => ReactNode
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
    <div
      className={cn(
        'rounded-2xl border border-dark-700/50 overflow-hidden',
        'bg-gradient-to-br from-dark-800/80 to-dark-900/90',
        'shadow-lg shadow-black/10',
        className,
      )}
    >
      {/* Header */}
      <div className="px-6 py-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-dark-100">{title}</h3>
        {viewAllHref && (
          <Link
            to={viewAllHref}
            className="text-[11px] font-medium text-primary-400 hover:text-primary-300 flex items-center gap-0.5 transition-colors"
          >
            Voir tout
            <ChevronRight className="w-3 h-3" />
          </Link>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-t border-dark-700/40">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    'px-6 py-2.5 text-[10px] font-semibold text-dark-500 uppercase tracking-wider whitespace-nowrap',
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
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-6 py-10 text-center text-dark-500 text-sm"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row, index) => (
                <tr
                  key={keyExtractor(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cn(
                    'border-t border-dark-700/20 transition-colors duration-150',
                    onRowClick
                      ? 'cursor-pointer hover:bg-white/[0.03] active:bg-white/[0.05]'
                      : 'hover:bg-white/[0.02]',
                  )}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={cn(
                        'px-6 py-3.5 whitespace-nowrap text-dark-200',
                        col.align === 'right' && 'text-right',
                        col.align === 'center' && 'text-center',
                        col.className,
                      )}
                    >
                      {col.render ? col.render(row, index) : String((row as Record<string, unknown>)[col.key] ?? '')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      {footer && (
        <div className="px-6 py-3.5 border-t border-dark-700/40 bg-dark-900/30">
          {footer}
        </div>
      )}
    </div>
  )
}
