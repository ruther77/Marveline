import type { ReservationDetailFull, SectionKey } from '@/types/reservation'
import type { Deposit } from '@/types/deposit'
import { CountdownChip } from '@shared/components/ui/CountdownChip'
import {
  ReservationHero,
  StatusAlert,
  ReservationInfoGrid,
  FieldTimeline,
  ProductLines,
  InvoiceSection,
  AssignSection,
  QuickLinks,
} from './components'
import { DepositSection } from '@/pages/events/components/DepositSection'
import { PreCheckSection } from '@/pages/events/components/PreCheckSection'
import { RisksSection } from '@/pages/events/components/RisksSection'
import { ExtendSection } from '@/pages/events/components/ExtendSection'
import { LegalDocsSection } from './components/LegalDocsSection'
import { DisputeLogTimeline } from './components/DisputeLogTimeline'

interface SectionRendererProps {
  sectionKey: SectionKey
  reservation: ReservationDetailFull
  deposits: Deposit[]
}

/**
 * Dispatch d'une section par sa clé — source unique pour le rendu.
 * Les mouvements sont chargés au niveau de ReservationView et passés à
 * FieldTimeline via contexte ou via un chargement local dans le sous-composant.
 */
export function SectionRenderer({ sectionKey, reservation, deposits }: SectionRendererProps) {
  const currentDeposit = deposits[0]
  const reservationId = reservation.id

  switch (sectionKey) {
    case 'hero':
      return <ReservationHero reservation={reservation} deposit={currentDeposit} />

    case 'status-alert':
      return <StatusAlert reservation={reservation} deposit={currentDeposit} />

    case 'info-grid':
      return <ReservationInfoGrid reservation={reservation} />

    case 'field-timeline':
      return <FieldTimeline reservation={reservation} />

    case 'product-lines':
      return <ProductLines reservation={reservation} />

    case 'deposit':
      return (
        <DepositSection
          reservation={reservation}
          reservationId={reservationId}
          currentDeposit={currentDeposit}
        />
      )

    case 'pre-check':
      return <PreCheckSection reservation={reservation} />

    case 'risks':
      return <RisksSection reservation={reservation} />

    case 'invoice':
      return (
        <InvoiceSection
          reservationId={reservationId}
          eventDate={reservation.event_date}
          status={reservation.status}
        />
      )

    case 'assign':
      return (
        <AssignSection
          reservationId={reservationId}
          assignedUserId={reservation.assigned_user_id ?? null}
          status={reservation.status}
        />
      )

    case 'quick-links':
      return <QuickLinks reservation={reservation} />

    case 'extend':
      return <ExtendSection reservation={reservation} />

    case 'countdown':
      return reservation.return_date ? (
        <div className="flex">
          <CountdownChip targetDate={reservation.return_date} />
        </div>
      ) : null

    case 'legal-docs':
      return <LegalDocsSection reservation={reservation} deposits={deposits} />

    case 'dispute-log':
      return <DisputeLogTimeline reservationId={reservationId} />

    default: {
      const _exhaustive: never = sectionKey
      return null
    }
  }
}
