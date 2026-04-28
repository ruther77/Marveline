import { useStockItemHistory } from '@/api/queries'
import { Modal } from '@shared/components/ui/Modal'
import { formatDate, cn } from '@/lib/utils'
import { Clock, ArrowRight } from 'lucide-react'
import {
  MOVEMENT_TYPE_LABELS,
  MOVEMENT_STATUS_LABELS,
} from '@/lib/constants'

interface StockItemHistoryModalProps {
  isOpen: boolean
  onClose: () => void
  productId?: number
  itemId?: number
}

// Badge statut stock avec bordure (variante enrichie de STOCK_ITEM_STATUS_COLORS)
const STATUS_LABELS: Record<string, string> = {
  available: 'Disponible',
  reserved: 'Réservé',
  on_location: 'En location',
  damaged: 'Endommagé',
  in_repair: 'En réparation',
  retired: 'Retiré',
}

const STATUS_COLORS: Record<string, string> = {
  available: 'bg-green-500/10 text-green-400 border-green-500/30',
  reserved: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  on_location: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
  damaged: 'bg-red-500/10 text-red-400 border-red-500/30',
  in_repair: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  retired: 'bg-dark-600 text-dark-400 border-dark-500',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border',
        STATUS_COLORS[status] || 'bg-dark-900 text-dark-400 border-dark-600'
      )}
    >
      {STATUS_LABELS[status] || status}
    </span>
  )
}

export function StockItemHistoryModal({
  isOpen,
  onClose,
  productId,
  itemId,
}: StockItemHistoryModalProps) {
  const { data: history, isLoading } = useStockItemHistory(
    isOpen && productId ? productId : null,
    isOpen && itemId ? itemId : null,
  )

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Historique — Unité #${itemId ?? '...'}`}
      size="md"
    >
      {isLoading ? (
        <div className="space-y-4 animate-pulse">
          <div className="h-10 skel rounded-lg" />
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 p-4 bg-dark-900 rounded-lg">
              <div className="w-6 h-6 skel rounded-full shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-40" />
                <div className="h-2 skel rounded w-28" />
              </div>
            </div>
          ))}
        </div>
      ) : history ? (
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center gap-4 p-4 bg-dark-900 rounded-lg">
            <div>
              <p className="text-xs text-dark-400">Unité #{history.stock_item_id}</p>
              {history.serial_number && (
                <p className="text-sm font-mono text-primary-400">{history.serial_number}</p>
              )}
            </div>
            <div className="ml-auto">
              <p className="text-xs text-dark-400 mb-0.5">Statut actuel</p>
              <StatusBadge status={history.current_status} />
            </div>
          </div>

          {/* Timeline */}
          {history.entries.length === 0 ? (
            <div className="text-center py-8 border border-dashed border-dark-600 rounded-lg">
              <Clock className="w-10 h-10 text-dark-600 mx-auto mb-2" />
              <p className="text-sm text-dark-400">Aucun mouvement enregistré</p>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-xs text-dark-500 uppercase tracking-wide">
                {history.entries.length} mouvement{history.entries.length > 1 ? 's' : ''}
              </p>
              <div className="relative">
                {/* Vertical line */}
                <div className="absolute left-3 top-4 bottom-4 w-px bg-dark-900" />

                <div className="space-y-4">
                  {history.entries.map((entry, i) => (
                    <div key={i} className="flex gap-4">
                      {/* Dot */}
                      <div className="flex-shrink-0 w-7 flex justify-center">
                        <div className={cn(
                          'w-2.5 h-2.5 rounded-full mt-1.5 border-2',
                          entry.movement_status === 'completed'
                            ? 'bg-green-500 border-green-500'
                            : entry.movement_status === 'cancelled'
                            ? 'bg-dark-600 border-dark-500'
                            : 'bg-primary-500 border-primary-500'
                        )} />
                      </div>

                      {/* Content */}
                      <div className="flex-1 pb-4">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={cn(
                            'text-xs font-medium px-1.5 py-0.5 rounded',
                            entry.movement_type === 'departure'
                              ? 'bg-orange-500/10 text-orange-400'
                              : 'bg-blue-500/10 text-blue-400'
                          )}>
                            {MOVEMENT_TYPE_LABELS[entry.movement_type] || entry.movement_type}
                          </span>
                          <span className="text-xs text-dark-500">
                            {MOVEMENT_STATUS_LABELS[entry.movement_status] || entry.movement_status}
                          </span>
                          <span className="text-xs text-dark-500 ml-auto">
                            {formatDate(entry.scheduled_date)}
                          </span>
                        </div>

                        {/* State transition */}
                        {(entry.status_before || entry.status_after) && (
                          <div className="flex items-center gap-2 mt-2">
                            {entry.status_before && <StatusBadge status={entry.status_before} />}
                            <ArrowRight className="w-3.5 h-3.5 text-dark-500 flex-shrink-0" />
                            {entry.status_after && <StatusBadge status={entry.status_after} />}
                          </div>
                        )}

                        {/* Condition */}
                        {entry.condition && (
                          <p className="text-xs text-dark-400 mt-1">
                            État: <span className="">{entry.condition}</span>
                            {entry.condition_notes && (
                              <span className="text-dark-500"> — {entry.condition_notes}</span>
                            )}
                          </p>
                        )}

                        {/* Actual date if different */}
                        {entry.actual_date && entry.actual_date !== entry.scheduled_date && (
                          <p className="text-xs text-dark-500 mt-0.5">
                            Effectué le {formatDate(entry.actual_date)}
                          </p>
                        )}

                        {entry.reservation_id && (
                          <p className="text-xs text-dark-500 mt-0.5">
                            Réservation #{entry.reservation_id}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-8 text-dark-400">Unité introuvable</div>
      )}
    </Modal>
  )
}
