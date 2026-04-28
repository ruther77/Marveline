import { cn } from '../../lib/utils'
import type { DevisStatus } from '../../types/devis'
import type { ReservationStatus } from '../../types/reservation'
import type { VenteStatus } from '../../types/vente'
import type { EventStatus } from '../../types/event'

type AnyDomainStatus = DevisStatus | ReservationStatus | VenteStatus | EventStatus

interface StatusConfig {
  label: string
  /** Classe CSS badge du design system (badge-green, badge-blue, etc.) */
  badge: string
}

const STATUS_MAP: Record<string, StatusConfig> = {
  // Commun
  draft:              { label: 'Brouillon',    badge: 'badge-muted' },
  cancelled:          { label: 'Annule',       badge: 'badge-red' },

  // Devis
  sent:               { label: 'Envoye',       badge: 'badge-blue' },
  negotiation:        { label: 'Negociation',  badge: 'badge-yellow' },
  accepted:           { label: 'Accepte',      badge: 'badge-green' },
  refused:            { label: 'Refuse',       badge: 'badge-red' },
  expired:            { label: 'Expire',       badge: 'badge-muted' },
  converted:          { label: 'Converti',     badge: 'badge-purple' },
  version_pending:    { label: 'Revision',     badge: 'badge-orange' },

  // Reservation
  confirmed:          { label: 'Confirme',     badge: 'badge-green' },
  confirmed_risk:     { label: 'Confirme',     badge: 'badge-orange' },
  pre_check:          { label: 'Pre-check',    badge: 'badge-blue' },
  delivered:          { label: 'Livre',        badge: 'badge-pink' },
  extended:           { label: 'Prolonge',     badge: 'badge-orange' },
  returned:           { label: 'Retourne',     badge: 'badge-muted' },
  returned_dispute:   { label: 'Litige',       badge: 'badge-red' },
  completed:          { label: 'Termine',      badge: 'badge-green' },

  // Vente
  pending:            { label: 'En attente',   badge: 'badge-yellow' },
  deposit_paid:       { label: 'Acompte verse', badge: 'badge-blue' },
  fully_paid:         { label: 'Paye',         badge: 'badge-green' },
  overdue:            { label: 'En retard',    badge: 'badge-red' },
  paid:               { label: 'Paye',         badge: 'badge-green' },
  refunded:           { label: 'Rembourse',    badge: 'badge-purple' },

  // Invoice
  // sent already mapped above

  // Event
  planned:            { label: 'Planifie',     badge: 'badge-blue' },
  risk:               { label: 'A risque',     badge: 'badge-orange' },
  in_progress:        { label: 'En cours',     badge: 'badge-pink' },
  incident:           { label: 'Incident',     badge: 'badge-red' },
  damage:             { label: 'Dommages',     badge: 'badge-red' },
  returning:          { label: 'Retour',       badge: 'badge-orange' },
  closed:             { label: 'Cloture',      badge: 'badge-muted' },

  // Mouvement stock
  scheduled:          { label: 'Planifié',     badge: 'badge-blue' },
  in_transit:         { label: 'En transit',   badge: 'badge-orange' },
}

export interface DomainStatusBadgeProps {
  status: AnyDomainStatus | string
  className?: string
  size?: 'sm' | 'md'
}

export function DomainStatusBadge({ status, className, size = 'sm' }: DomainStatusBadgeProps) {
  const cfg = STATUS_MAP[status] ?? { label: status, badge: 'badge-muted' }

  return (
    <span
      className={cn(
        'badge',
        size === 'md' && 'text-sm px-2.5 py-1',
        cfg.badge,
        className
      )}
    >
      {cfg.label}
    </span>
  )
}
