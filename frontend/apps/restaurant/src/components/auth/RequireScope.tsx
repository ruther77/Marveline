import type { ReactNode } from 'react'
import { useRestaurantScopes } from '../../hooks/useRestaurantScopes'

type ScopeCheck = 'read' | 'edit' | 'manager'

interface RequireScopeProps {
  scope: ScopeCheck
  children: ReactNode
  fallback?: ReactNode
}

export function RequireScope({ scope, children, fallback = null }: RequireScopeProps) {
  const { canRead, canEdit, isManager } = useRestaurantScopes()

  const allowed =
    scope === 'read' ? canRead : scope === 'edit' ? canEdit : isManager

  if (!allowed) return <>{fallback}</>
  return <>{children}</>
}

export function ReadOnlyBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
      <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
      </svg>
      Lecture seule
    </span>
  )
}
