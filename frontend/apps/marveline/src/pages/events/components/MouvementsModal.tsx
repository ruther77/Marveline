import { BottomSheet as Modal } from '@shared/components/ui/BottomSheet'
import { Link } from '@tanstack/react-router'
import { useMovementsList } from '@/api/queries/useInventory'
import { DomainStatusBadge } from '@shared/components/ui'
import { formatDate } from '@/lib/utils'
import { ArrowUp, ArrowDown } from 'lucide-react'

interface Props {
  isOpen: boolean
  onClose: () => void
  reservationId: number
}

export function MouvementsModal({ isOpen, onClose, reservationId }: Props) {
  const { data, isLoading } = useMovementsList({ reservation_id: reservationId, limit: 20 }, isOpen)
  const movements = data?.items ?? []

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Mouvements (${movements.length})`} size="md">
      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2].map((i) => <div key={i} className="h-12 bg-dark-900 rounded" />)}
        </div>
      ) : movements.length === 0 ? (
        <p className="text-sm text-dark-400 py-8 text-center">Aucun mouvement</p>
      ) : (
        <div className="space-y-2">
          {movements.map((mv) => {
            const isDeparture = mv.movement_type === 'departure'
            const opUrl = isDeparture
              ? `/operations/departure/${reservationId}`
              : `/operations/return/${reservationId}`

            return (
              <Link
                key={mv.id}
                to={opUrl as never}
                className="flex items-center gap-3 p-3 rounded-lg bg-dark-900 hover:bg-dark-600 transition-colors"
              >
                {isDeparture
                  ? <ArrowUp className="w-4 h-4 text-blue-400 shrink-0" />
                  : <ArrowDown className="w-4 h-4 text-orange-400 shrink-0" />
                }
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">
                    {isDeparture ? 'Départ' : 'Retour'} #{mv.id}
                  </p>
                  <p className="text-xs text-dark-400">{formatDate(mv.scheduled_date)}</p>
                </div>
                <DomainStatusBadge status={mv.status} />
              </Link>
            )
          })}
        </div>
      )}
    </Modal>
  )
}
