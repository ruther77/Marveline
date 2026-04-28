import { LayoutList, LayoutGrid } from 'lucide-react'
import { cn } from '../../lib/utils'

export type ViewMode = 'table' | 'grid'

const STORAGE_KEY = 'catalogue-view-mode'

export function getStoredViewMode(): ViewMode {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'grid' ? 'grid' : 'table'
}

export function setStoredViewMode(mode: ViewMode) {
  localStorage.setItem(STORAGE_KEY, mode)
}

interface ViewToggleProps {
  mode: ViewMode
  onChange: (mode: ViewMode) => void
  className?: string
}

export function ViewToggle({ mode, onChange, className }: ViewToggleProps) {
  return (
    <div className={cn('flex items-center bg-dark-900 rounded-lg border border-dark-600 p-0.5', className)}>
      <button
        type="button"
        onClick={() => onChange('table')}
        className={cn(
          'flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm transition-colors',
          mode === 'table'
            ? 'bg-primary-600 text-white'
            : 'text-dark-400 hover:text-dark-50'
        )}
        aria-label="Vue tableau"
      >
        <LayoutList className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={() => onChange('grid')}
        className={cn(
          'flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm transition-colors',
          mode === 'grid'
            ? 'bg-primary-600 text-white'
            : 'text-dark-400 hover:text-dark-50'
        )}
        aria-label="Vue grille"
      >
        <LayoutGrid className="w-4 h-4" />
      </button>
    </div>
  )
}
