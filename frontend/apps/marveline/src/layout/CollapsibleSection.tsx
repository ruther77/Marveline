import { useState, type ComponentType, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CollapsibleSectionProps {
  /** Titre de la section */
  title: string
  /** Icone optionnelle (Lucide component) */
  icon?: ComponentType<{ className?: string }>
  /** Badge compteur optionnel */
  badge?: number
  /** Ouverte par defaut */
  defaultOpen?: boolean
  /** Contenu de la section */
  children: ReactNode
  /** Classes additionnelles sur le wrapper */
  className?: string
}

/**
 * Section accordeon avec titre + chevron.
 * Remplace les tabs par du scroll vertical — mobile first.
 */
export function CollapsibleSection({
  title,
  icon: Icon,
  badge,
  defaultOpen = false,
  children,
  className,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className={cn('border border-dark-600 rounded-xl overflow-hidden', className)}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-dark-600/50 transition-colors"
      >
        {Icon && (
          <div className="w-7 h-7 card border border-dark-600 flex items-center justify-center shrink-0">
            <Icon className="w-3.5 h-3.5 text-dark-400" />
          </div>
        )}
        <span className="flex-1 text-sm font-semibold">{title}</span>
        {badge !== undefined && badge > 0 && (
          <span className="px-1.5 py-0.5 text-xs rounded-full bg-primary-500/10 text-primary-400 font-medium">
            {badge}
          </span>
        )}
        <ChevronDown
          className={cn(
            'w-4 h-4 text-dark-500 transition-transform duration-200',
            open && 'rotate-180',
          )}
        />
      </button>
      <div
        className={cn(
          'transition-all duration-200 ease-in-out',
          open ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0 overflow-hidden',
        )}
      >
        <div className="px-4 pb-4 pt-1">
          {children}
        </div>
      </div>
    </div>
  )
}
