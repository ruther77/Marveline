import { ChevronLeft, ChevronRight } from 'lucide-react'

interface PaginationProps {
  page: number
  total: number
  perPage: number
  onPageChange: (page: number) => void
  itemLabel?: string
  className?: string
}

export function Pagination({
  page,
  total,
  perPage,
  onPageChange,
  itemLabel = 'élément',
  className = '',
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / perPage))
  if (totalPages <= 1) return null

  const plural = total > 1 ? 's' : ''
  const start = (page - 1) * perPage + 1
  const end = Math.min(page * perPage, total)

  return (
    <div className={`flex items-center justify-between gap-3 text-[13px] ${className}`}>
      <span className="text-slate-500">
        {start}–{end} sur {total} {itemLabel}{plural}
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={page === 1}
          onClick={() => onPageChange(page - 1)}
          aria-label="Page précédente"
          className="min-w-11 min-h-11 px-3 inline-flex items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="text-slate-600 tabular-nums">
          {page} / {totalPages}
        </span>
        <button
          type="button"
          disabled={page === totalPages}
          onClick={() => onPageChange(page + 1)}
          aria-label="Page suivante"
          className="min-w-11 min-h-11 px-3 inline-flex items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
