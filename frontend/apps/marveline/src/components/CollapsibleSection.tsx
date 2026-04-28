import { useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CollapsibleSectionProps {
  title: string
  subtitle?: string
  icon?: ReactNode
  badge?: ReactNode
  defaultOpen?: boolean
  children: ReactNode
  className?: string
}

export function CollapsibleSection({
  title,
  subtitle,
  icon,
  badge,
  defaultOpen = true,
  children,
  className,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className={cn('card overflow-hidden', className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-dark-800/30 transition-colors"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {icon && <span className="text-dark-400 shrink-0">{icon}</span>}
          <div className="min-w-0 text-left">
            <span className="text-sm font-semibold text-dark-100">{title}</span>
            {subtitle && <span className="text-xs text-dark-400 ml-2">{subtitle}</span>}
          </div>
          {badge && <span className="shrink-0">{badge}</span>}
        </div>
        <ChevronDown
          className={cn(
            'w-4 h-4 text-dark-400 transition-transform shrink-0',
            open && 'rotate-180',
          )}
        />
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  )
}
