import { BottomSheet as Modal } from '@shared/components/ui/BottomSheet'
import { RisksSection } from './RisksSection'
import type { ReservationDetail } from '@/types/reservation'

interface Props {
  isOpen: boolean
  onClose: () => void
  reservation: ReservationDetail
}

export function RisquesModal({ isOpen, onClose, reservation }: Props) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Risques" size="md">
      <RisksSection reservation={reservation} />
    </Modal>
  )
}
