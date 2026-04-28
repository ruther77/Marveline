import { BottomSheet as Modal } from '@shared/components/ui/BottomSheet'
import { PreCheckSection } from './PreCheckSection'
import type { ReservationDetail } from '@/types/reservation'

interface Props {
  isOpen: boolean
  onClose: () => void
  reservation: ReservationDetail
}

export function PreCheckModal({ isOpen, onClose, reservation }: Props) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Pre-check" size="md">
      <PreCheckSection reservation={reservation} />
    </Modal>
  )
}
