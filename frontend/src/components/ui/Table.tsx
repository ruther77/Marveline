import { ReactNode } from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { cn } from '../../lib/utils';

// Types
export type SortDirection = 'asc' | 'desc' | null;

export interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  width?: string;
  align?: 'left' | 'center' | 'right';
  render?: (item: T, index: number) => ReactNode;
}

export interface TableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyExtractor: (item: T) => string | number;
  sortKey?: string;
  sortDirection?: SortDirection;
  onSort?: (key: string) => void;
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
  selectedKey?: string | number;
  stickyHeader?: boolean;
}

export function Table<T>({
  data,
  columns,
  keyExtractor,
  sortKey,
  sortDirection,
  onSort,
  loading = false,
  emptyMessage = 'Aucune donnée',
  onRowClick,
  selectedKey,
  stickyHeader = false,
}: TableProps<T>) {
  const renderSortIcon = (column: Column<T>) => {
    if (!column.sortable) return null;

    if (sortKey === column.key) {
      return sortDirection === 'asc' ? (
        <ChevronUp className="w-4 h-4" />
      ) : (
        <ChevronDown className="w-4 h-4" />
      );
    }
    return <ChevronsUpDown className="w-4 h-4 opacity-50" />;
  };

  const alignClass = {
    left: 'text-left',
    center: 'text-center',
    right: 'text-right',
  };

  return (
    <div className="overflow-x-auto rounded-lg border border-dark-700">
      <table className="w-full">
        <thead className={cn(
          'bg-dark-800',
          stickyHeader && 'sticky top-0 z-10'
        )}>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  'px-4 py-3 text-xs font-semibold text-dark-300 uppercase tracking-wider',
                  alignClass[column.align || 'left'],
                  column.sortable && 'cursor-pointer hover:text-white transition-colors select-none',
                  column.width
                )}
                style={column.width ? { width: column.width } : undefined}
                onClick={column.sortable && onSort ? () => onSort(column.key) : undefined}
              >
                <div className={cn(
                  'flex items-center gap-1',
                  column.align === 'center' && 'justify-center',
                  column.align === 'right' && 'justify-end'
                )}>
                  {column.header}
                  {renderSortIcon(column)}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-dark-700">
          {loading ? (
            // Skeleton loading
            Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="bg-dark-900">
                {columns.map((column) => (
                  <td key={column.key} className="px-4 py-3">
                    <div className="h-4 bg-dark-700 rounded animate-pulse" />
                  </td>
                ))}
              </tr>
            ))
          ) : data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-12 text-center text-dark-400"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((item, index) => {
              const key = keyExtractor(item);
              const isSelected = selectedKey === key;

              return (
                <tr
                  key={key}
                  className={cn(
                    'bg-dark-900 transition-colors',
                    onRowClick && 'cursor-pointer hover:bg-dark-800',
                    isSelected && 'bg-primary-900/20'
                  )}
                  onClick={onRowClick ? () => onRowClick(item) : undefined}
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        'px-4 py-3 text-sm text-dark-200',
                        alignClass[column.align || 'left']
                      )}
                    >
                      {column.render
                        ? column.render(item, index)
                        : (item as Record<string, unknown>)[column.key]?.toString() ?? '-'}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

// Pagination Component
export interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  total?: number;
  perPage?: number;
}

export function Pagination({
  page,
  totalPages,
  onPageChange,
  total,
  perPage,
}: PaginationProps) {
  const start = total ? (page - 1) * (perPage || 10) + 1 : 0;
  const end = total ? Math.min(page * (perPage || 10), total) : 0;

  return (
    <div className="flex items-center justify-between px-4 py-3 bg-dark-800 border-t border-dark-700 rounded-b-lg">
      <div className="text-sm text-dark-400">
        {total ? (
          <>
            <span className="font-medium text-white">{start}</span>
            {' - '}
            <span className="font-medium text-white">{end}</span>
            {' sur '}
            <span className="font-medium text-white">{total}</span>
          </>
        ) : (
          `Page ${page} sur ${totalPages}`
        )}
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className={cn(
            'px-3 py-1.5 text-sm font-medium rounded-lg transition-colors',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'bg-dark-700 text-dark-300 hover:bg-dark-600 hover:text-white'
          )}
        >
          Précédent
        </button>
        <div className="flex items-center gap-1">
          {generatePageNumbers(page, totalPages).map((pageNum, i) =>
            pageNum === '...' ? (
              <span key={`ellipsis-${i}`} className="px-2 text-dark-500">
                ...
              </span>
            ) : (
              <button
                key={pageNum}
                onClick={() => onPageChange(pageNum as number)}
                className={cn(
                  'w-8 h-8 text-sm font-medium rounded-lg transition-colors',
                  pageNum === page
                    ? 'bg-primary-600 text-white'
                    : 'bg-dark-700 text-dark-300 hover:bg-dark-600 hover:text-white'
                )}
              >
                {pageNum}
              </button>
            )
          )}
        </div>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className={cn(
            'px-3 py-1.5 text-sm font-medium rounded-lg transition-colors',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'bg-dark-700 text-dark-300 hover:bg-dark-600 hover:text-white'
          )}
        >
          Suivant
        </button>
      </div>
    </div>
  );
}

function generatePageNumbers(current: number, total: number): (number | string)[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | string)[] = [];

  if (current <= 3) {
    pages.push(1, 2, 3, 4, '...', total);
  } else if (current >= total - 2) {
    pages.push(1, '...', total - 3, total - 2, total - 1, total);
  } else {
    pages.push(1, '...', current - 1, current, current + 1, '...', total);
  }

  return pages;
}
