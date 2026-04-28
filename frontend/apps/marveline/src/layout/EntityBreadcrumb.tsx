import { useNavigate } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { Breadcrumb, type BreadcrumbItem } from '@shared/components/ui/Breadcrumb'
import { useBackNavigation } from '@/hooks/useBackNavigation'

interface EntityBreadcrumbProps {
  /** Breadcrumb items (parent → ... → current). Le dernier = page courante (non-cliquable). */
  items: BreadcrumbItem[]
  /** URL du bouton retour. Si omis, utilise useBackNavigation() (mapping automatique). */
  backTo?: string
  /** Params TanStack Router pour backTo (ex: { id: '123' }) */
  backParams?: Record<string, string>
  /** Label pour l'accessibilite du bouton retour */
  backLabel?: string
}

/**
 * Breadcrumb avec bouton retour integre.
 * Mobile : affiche uniquement back + nom entite courante.
 * Desktop : affiche le fil d'Ariane complet.
 *
 * Si backTo n'est pas fourni, le hook useBackNavigation determine
 * automatiquement la destination logique selon la route courante.
 */
export function EntityBreadcrumb({ items, backTo, backParams, backLabel = 'Retour' }: EntityBreadcrumbProps) {
  const navigate = useNavigate()
  const { goBack, backTo: autoBackTo } = useBackNavigation()
  const resolvedBackTo = backTo ?? autoBackTo

  const handleBack = () => {
    if (backTo) {
      navigate({ to: backTo as never, params: backParams as never })
    } else {
      goBack()
    }
  }

  return (
    <div className="flex items-center gap-2 mb-4">
      <button
        onClick={handleBack}
        className="p-1.5 -ml-1.5 rounded-lg hover:bg-dark-600 transition-colors shrink-0"
        aria-label={backLabel}
      >
        <ArrowLeft className="w-4 h-4 text-dark-400" />
      </button>

      {/* Mobile : dernier item seulement */}
      <span className="md:hidden text-sm font-medium truncate">
        {items[items.length - 1]?.label ?? ''}
      </span>

      {/* Desktop : breadcrumb complet */}
      <Breadcrumb items={items} showHome={false} className="hidden md:block" />
    </div>
  )
}

/**
 * Bouton retour simple (sans breadcrumb).
 * Utilise le mapping automatique useBackNavigation.
 * A utiliser dans les pages qui n'ont pas besoin d'un fil d'Ariane complet.
 */
export function BackButton({ label }: { label?: string }) {
  const { goBack } = useBackNavigation()

  return (
    <button
      onClick={goBack}
      className="flex items-center gap-1.5 p-1.5 -ml-1.5 rounded-lg text-dark-400 hover:text-dark-200 hover:bg-dark-600 transition-colors"
      aria-label="Retour"
    >
      <ArrowLeft className="w-4 h-4" />
      {label && <span className="text-sm">{label}</span>}
    </button>
  )
}
