import type { ComponentType } from 'react'
import { Link } from '@tanstack/react-router'
import { cn } from '@/lib/utils'

export interface EntityLink {
  /** Label affiche (ex: "Client: Dupont", "Devis DEV-045") */
  label: string
  /** Route TanStack Router */
  href: string
  /** Params si route dynamique */
  params?: Record<string, string>
  /** Icone Lucide */
  icon?: ComponentType<{ className?: string }>
  /** Couleur du chip */
  color?: 'default' | 'green' | 'blue' | 'orange' | 'red'
}

interface EntityContextBarProps {
  links: EntityLink[]
  className?: string
}

const COLOR_MAP = {
  default: 'bg-dark-900 border-dark-600 text-dark-300 hover:bg-dark-600 hover:text-dark-100',
  green:   'bg-green-500/10 border-green-500/20 text-green-400 hover:bg-green-500/20',
  blue:    'bg-blue-500/10 border-blue-500/20 text-blue-400 hover:bg-blue-500/20',
  orange:  'bg-orange-500/10 border-orange-500/20 text-orange-400 hover:bg-orange-500/20',
  red:     'bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20',
}

/**
 * Barre horizontale scrollable de chips montrant les entites liees.
 * Pattern inspire de QuickLinks mais generique.
 *
 * Exemple :
 *   <EntityContextBar links={[
 *     { label: 'Client: Dupont', href: '/customers/$id', params: { id: '5' }, icon: User },
 *     { label: 'Devis DEV-045', href: '/devis/$id', params: { id: '45' }, icon: FileText, color: 'blue' },
 *   ]} />
 */
export function EntityContextBar({ links, className }: EntityContextBarProps) {
  if (links.length === 0) return null

  return (
    <div className={cn('flex gap-2 flex-wrap pb-1 lg:flex-nowrap lg:overflow-x-auto lg:scrollbar-none', className)}>
      {links.map((link) => {
        const Icon = link.icon
        const colorCls = COLOR_MAP[link.color ?? 'default']

        return (
          <Link
            key={link.label}
            to={link.href as never}
            params={link.params as never}
            className={cn(
              'inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border rounded-full whitespace-nowrap transition-colors shrink-0',
              colorCls,
            )}
          >
            {Icon && <Icon className="w-3 h-3" />}
            {link.label}
          </Link>
        )
      })}
    </div>
  )
}
