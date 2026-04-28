import { BottomSheet as Modal } from '@shared/components/ui/BottomSheet'
import { ExtendSection } from './ExtendSection'
import type { ReservationDetail } from '@/types/reservation'

interface Props {
  isOpen: boolean
  onClose: () => void
  reservation: ReservationDetail
}

export function ExtensionModal({ isOpen, onClose, reservation }: Props) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Prolonger la réservation" size="md">
      <ExtendSection reservation={reservation} />
    </Modal>
  )
}
