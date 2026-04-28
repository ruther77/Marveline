import { BottomSheet as Modal } from '@shared/components/ui/BottomSheet'
import { useEntityAuditLogs } from '@/api/queries/admin/useAuditLogs'
import { formatDate } from '@/lib/utils'

interface Props {
  isOpen: boolean
  onClose: () => void
  reservationId: number
}

export function HistoriqueModal({ isOpen, onClose, reservationId }: Props) {
  const { data, isLoading } = useEntityAuditLogs('Reservation', isOpen ? reservationId : null)
  const logs = data?.items ?? data ?? []
  const entries = Array.isArray(logs) ? logs : []

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Historique (${entries.length})`} size="lg">
      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3].map((i) => <div key={i} className="h-10 bg-dark-900 rounded" />)}
        </div>
      ) : entries.length === 0 ? (
        <p className="text-sm text-dark-400 py-8 text-center">Aucun historique</p>
      ) : (
        <div className="space-y-0 divide-y divide-dark-600">
          {entries.map((entry, idx) => (
            <div key={entry.id ?? idx} className="flex items-start gap-3 py-3">
              <div className="w-2 h-2 rounded-full bg-primary-500 mt-1.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm">{entry.action || entry.description || '—'}</p>
                <p className="text-xs text-dark-400">
                  {formatDate(entry.created_at)} — {entry.user_id ? `Utilisateur #${entry.user_id}` : 'Système'}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}
