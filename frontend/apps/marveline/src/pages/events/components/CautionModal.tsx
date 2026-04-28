import { BottomSheet as Modal } from '@shared/components/ui/BottomSheet'
import { DepositSection } from './DepositSection'
import type { ReservationDetail } from '@/types/reservation'
import type { Deposit } from '@/types/deposit'

interface Props {
  isOpen: boolean
  onClose: () => void
  reservation: ReservationDetail
  currentDeposit?: Deposit
}

export function CautionModal({ isOpen, onClose, reservation, currentDeposit }: Props) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Caution" size="md">
      <DepositSection
        reservation={reservation}
        reservationId={reservation.id}
        currentDeposit={currentDeposit}
      />
    </Modal>
  )
}
