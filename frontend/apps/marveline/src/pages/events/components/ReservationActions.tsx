import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { MoreVertical, Truck, RotateCcw, Check, XCircle, Archive, Trash2, Edit, Bell } from 'lucide-react'
import {
  useConfirmReservation,
  useCancelReservation,
  useCompleteReservation,
  useArchiveReservation,
  useDeleteReservation,
} from '@/api/queries'
import { normalizeError } from '@shared/errors/normalizer'
import type { ReservationDetail } from '@/types/reservation'
import { CancelReservationModal } from './CancelReservationModal'
import { DeleteReservationModal } from './DeleteReservationModal'
import { ArchiveReservationModal } from './ArchiveReservationModal'

interface Props {
  reservation: ReservationDetail
}

export function ReservationActions({ reservation }: Props) {
  const navigate = useNavigate()
  const r = reservation
  const [menuOpen, setMenuOpen] = useState(false)
  const [cancelModal, setCancelModal] = useState(false)
  const [deleteModal, setDeleteModal] = useState(false)
  const [archiveModal, setArchiveModal] = useState(false)

  const confirmMut = useConfirmReservation()
  const cancelMut = useCancelReservation()
  const completeMut = useCompleteReservation()
  const archiveMut = useArchiveReservation()
  const deleteMut = useDeleteReservation()

  const goDepart = () => navigate({ to: '/operations/departure/$reservationId', params: { reservationId: String(r.id) } })
  const goReturn = () => navigate({ to: '/operations/return/$reservationId', params: { reservationId: String(r.id) } })
  const goEdit = () => navigate({ to: '/reservations/$id/edit', params: { id: String(r.id) } })

  const primaryAction = (): { label: string; icon: typeof Check; onClick: () => void; className: string } | null => {
    switch (r.status) {
      case 'draft':
        return { label: 'Confirmer', icon: Check, onClick: () => confirmMut.mutate(r.id), className: 'bg-green-600 hover:bg-green-700' }
      case 'confirmed':
      case 'confirmed_risk':
        return { label: 'Confirmer', icon: Check, onClick: () => confirmMut.mutate(r.id), className: 'bg-green-600 hover:bg-green-700' }
      case 'pre_check':
        return { label: 'Procéder au départ', icon: Truck, onClick: goDepart, className: 'bg-green-600 hover:bg-green-700' }
      case 'delivered':
      case 'extended':
        return { label: 'Enregistrer retour', icon: RotateCcw, onClick: goReturn, className: 'bg-blue-600 hover:bg-blue-700' }
      case 'returned':
        return { label: 'Clôturer', icon: Check, onClick: () => completeMut.mutate(r.id), className: 'bg-green-600 hover:bg-green-700' }
      case 'completed':
        return !r.is_archived ? { label: 'Archiver', icon: Archive, onClick: () => setArchiveModal(true), className: 'bg-dark-600 hover:bg-dark-500' } : null
      default:
        return null
    }
  }

  const secondaryActions = (): { label: string; icon: typeof Check; onClick: () => void; danger?: boolean }[] => {
    const actions: { label: string; icon: typeof Check; onClick: () => void; danger?: boolean }[] = []
    if (r.status === 'draft') {
      actions.push({ label: 'Modifier', icon: Edit, onClick: goEdit })
      actions.push({ label: 'Supprimer', icon: Trash2, onClick: () => setDeleteModal(true), danger: true })
    }
    if (['draft', 'confirmed', 'confirmed_risk'].includes(r.status)) {
      actions.push({ label: 'Annuler', icon: XCircle, onClick: () => setCancelModal(true), danger: true })
    }
    if (r.status === 'returned') {
      actions.push({ label: 'Ouvrir litige', icon: Bell, onClick: () => {/* handled in CloseDisputeModal */}, danger: true })
    }
    return actions
  }

  const primary = primaryAction()
  const secondary = secondaryActions()
  const error = confirmMut.error || cancelMut.error || completeMut.error || archiveMut.error || deleteMut.error

  return (
    <>
      <div className="flex items-center gap-2">
        {primary && (
          <button
            type="button"
            onClick={primary.onClick}
            disabled={confirmMut.isPending || completeMut.isPending}
            className={`flex items-center gap-1.5 text-white text-sm font-semibold px-4 py-2 rounded-lg shrink-0 disabled:opacity-50 ${primary.className}`}
          >
            <primary.icon className="w-4 h-4" />
            {primary.label}
          </button>
        )}

        {secondary.length > 0 && (
          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen(!menuOpen)}
              className="p-2 rounded-lg hover:bg-dark-600 text-dark-400 hover:text-dark-50 transition-colors"
            >
              <MoreVertical className="w-4 h-4" />
            </button>

            {menuOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 top-full mt-1 z-50 w-48 card shadow-lg py-1">
                  {secondary.map((item) => (
                    <button
                      key={item.label}
                      type="button"
                      onClick={() => { setMenuOpen(false); item.onClick() }}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-dark-600 transition-colors ${item.danger ? 'text-red-400' : 'text-dark-200'}`}
                    >
                      <item.icon className="w-4 h-4" />
                      {item.label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-400 mt-1">{normalizeError(error).message || 'Une erreur est survenue'}</p>
      )}

      {cancelModal && (
        <CancelReservationModal
          isOpen
          onClose={() => setCancelModal(false)}
          onConfirm={() => cancelMut.mutate(r.id, { onSuccess: () => setCancelModal(false) })}
          loading={cancelMut.isPending}
          reference={r.reference}
        />
      )}

      {deleteModal && (
        <DeleteReservationModal
          isOpen
          onClose={() => setDeleteModal(false)}
          onConfirm={() => deleteMut.mutate(r.id, { onSuccess: () => navigate({ to: '/reservations' }) })}
          loading={deleteMut.isPending}
          reference={r.reference}
        />
      )}

      {archiveModal && (
        <ArchiveReservationModal
          isOpen
          onClose={() => setArchiveModal(false)}
          onConfirm={() => archiveMut.mutate(r.id, { onSuccess: () => setArchiveModal(false) })}
          loading={archiveMut.isPending}
          reference={r.reference}
        />
      )}
    </>
  )
}
