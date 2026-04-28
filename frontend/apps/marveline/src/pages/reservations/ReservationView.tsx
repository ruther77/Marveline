import { ReservationPhaseSkeleton } from '@shared/components/ui/SkeletonPatterns'
import { useCurrentReservation } from './hooks/useCurrentReservation'
import { PHASE_SECTIONS } from './PHASE_MATRIX'
import { SectionRenderer } from './SectionRenderer'
import { ReservationActions } from './ReservationActions'

/**
 * Vue unifiée d'une réservation. Remplace les 13 pages de phase :
 *
 *   1. Charge la réservation via useCurrentReservation (useReservationFull + deposits)
 *   2. Dérive la phase
 *   3. Rend la séquence de sections définies dans PHASE_MATRIX
 *   4. Rend les CTAs contextuels via ReservationActions
 *
 * Les 13 routes URL `/reservations/$id/{phase}` restent bookmarkables : elles
 * rendent toutes ce même composant, la phase étant dérivée côté serveur via
 * derivePhase et synchronisée à l'URL par EventIdLayout.
 */
export default function ReservationView() {
  const { reservation, deposits, phase, isLoading } = useCurrentReservation()

  if (isLoading || !reservation || !phase) {
    return <ReservationPhaseSkeleton />
  }

  const sections = PHASE_SECTIONS[phase]

  return (
    <div className="space-y-4 pb-24 md:pb-4">
      {sections.map((sectionKey) => (
        <SectionRenderer
          key={sectionKey}
          sectionKey={sectionKey}
          reservation={reservation}
          deposits={deposits}
        />
      ))}

      {/* Desktop : inline dans le flow */}
      <div className="hidden md:block">
        <ReservationActions reservation={reservation} phase={phase} deposits={deposits} />
      </div>

      {/*
        Mobile : sticky en bas d'écran pour thumb zone (ui-ux.md §V).
        pb-24 sur le conteneur crée l'espace pour ne pas cacher la dernière section.
      */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-30 bg-dark-900/95 backdrop-blur-sm border-t border-dark-700 px-4 py-3 shadow-[0_-4px_20px_rgba(0,0,0,0.4)]">
        <ReservationActions reservation={reservation} phase={phase} deposits={deposits} />
      </div>
    </div>
  )
}
