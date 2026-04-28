import { Link } from '@tanstack/react-router'
import { Pen, Package } from 'lucide-react'
import type { ReservationDetail } from '@/types/reservation'

interface QuickLinksProps {
  reservation: Pick<ReservationDetail, 'id' | 'status' | 'signature_url' | 'devis_id'>
}

export function QuickLinks({ reservation }: QuickLinksProps) {
  const { id, status, signature_url, devis_id } = reservation
  const sid = String(id)

  const links: { label: string; to: string; icon: typeof Pen; params?: Record<string, string> }[] = []

  if (status === 'draft') {
    links.push({ label: 'Gérer les lignes', to: '/reservations/$id/lines', icon: Package, params: { id: sid } })
    links.push({ label: 'Modifier', to: '/reservations/$id/edit', icon: Pen, params: { id: sid } })
  }

  if (!signature_url && status !== 'cancelled' && status !== 'completed') {
    links.push({ label: 'Signer le contrat', to: '/reservations/$id/signature', icon: Pen, params: { id: sid } })
  }

  // "Pré-check légal" et "Départ opérationnel" sont gérés en inline
  // dans ConfirmeePage, PretePage et PrecheckPage — pas de doublon ici.

  // "Enregistrer le retour" est affiché directement dans EnCoursPage/ProlongeePage
  // pour les statuts delivered/extended — pas de doublon ici.

  // Le lien vers le devis est déjà affiché dans ReservationHero — pas de doublon ici.

  if (links.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2">
      {links.map((l) => (
        <Link
          key={l.label}
          to={l.to as never}
          params={l.params as never}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-dark-300 card hover:bg-dark-600 hover:text-dark-100 transition-colors"
        >
          <l.icon className="w-3 h-3" />
          {l.label}
        </Link>
      ))}
    </div>
  )
}
