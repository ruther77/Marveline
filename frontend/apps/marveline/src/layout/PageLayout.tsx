import type { ReactNode } from 'react'

interface PageLayoutProps {
  children: ReactNode
  sidebar?: ReactNode
  /** max-w-7xl (listes) ou max-w-5xl (detail/formulaire) */
  variant?: 'wide' | 'default'
  className?: string
}

/**
 * Layout desktop standard.
 * - Desktop (lg+) : grille 4 colonnes, contenu 3/4 + sidebar 1/4
 * - Mobile : 1 colonne, sidebar sous le contenu
 * - Si pas de sidebar, contenu prend toute la largeur
 */
export function PageLayout({ children, sidebar, variant = 'wide', className = '' }: PageLayoutProps) {
  const maxW = variant === 'wide' ? 'max-w-7xl' : 'max-w-5xl'

  if (!sidebar) {
    return (
      <div className={`${maxW} mx-auto space-y-6 ${className}`}>
        {children}
      </div>
    )
  }

  return (
    <div className={`${maxW} mx-auto ${className}`}>
      <div className="lg:grid lg:grid-cols-4 lg:gap-6">
        <div className="lg:col-span-3 space-y-6">
          {children}
        </div>
        <div className="mt-6 lg:mt-0 lg:col-span-1">
          <div className="lg:sticky lg:top-20 space-y-4">
            {sidebar}
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Card avec fond blanc casse standard.
 */
export function PageCard({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`card rounded-xl p-4 lg:p-6 ${className}`}>
      {children}
    </div>
  )
}
