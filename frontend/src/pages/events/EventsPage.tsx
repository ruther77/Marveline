import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reservationsApi } from '@/api/reservations'
import { useMultiModal } from '@/hooks/useModal'
import { ReservationFormModal, ReservationDetailsModal } from './components'
import type { ReservationList, ReservationStatus } from '@/types/reservation'
import {
  CalendarCheck,
  Plus,
  Eye,
  Check,
  XCircle,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { cn, formatDate } from '@/lib/utils'

type ModalType = 'create' | 'edit' | 'details'

const STATUS_LABELS: Record<ReservationStatus, string> = {
  draft: 'Brouillon',
  confirmed: 'Confirmee',
  delivered: 'Livree',
  returned: 'Retournee',
  cancelled: 'Annulee',
}

const STATUS_COLORS: Record<ReservationStatus, string> = {
  draft: 'bg-dark-700 text-dark-300',
  confirmed: 'bg-blue-500/10 text-blue-500',
  delivered: 'bg-orange-500/10 text-orange-500',
  returned: 'bg-green-500/10 text-green-500',
  cancelled: 'bg-red-500/10 text-red-500',
}

export default function ReservationsPage() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<ReservationStatus | ''>('')
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const queryClient = useQueryClient()

  const modal = useMultiModal<ReservationList>()

  const { data, isLoading } = useQuery({
    queryKey: ['reservations', page, statusFilter],
    queryFn: () =>
      reservationsApi.getReservations({
        page,
        page_size: 20,
        status: statusFilter || undefined,
      }),
  })

  const confirmMutation = useMutation({
    mutationFn: (id: number) => reservationsApi.confirmReservation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reservations'] })
    },
  })

  const cancelMutation = useMutation({
    mutationFn: (id: number) => reservationsApi.cancelReservation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reservations'] })
    },
  })

  const reservations = data?.items || []
  const totalPages = data?.total_pages || 1

  const handleOpenModal = (type: ModalType, reservation?: ReservationList) => {
    setOpenMenuId(null)
    modal.open(type, reservation as ReservationList)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Reservations</h1>
          <p className="text-dark-400 mt-1">
            Gerez les reservations et locations
          </p>
        </div>
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Nouvelle reservation
        </button>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex gap-4 flex-wrap">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as ReservationStatus | '')
              setPage(1)
            }}
            className="input"
          >
            <option value="">Tous les statuts</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          {statusFilter && (
            <button
              onClick={() => {
                setStatusFilter('')
                setPage(1)
              }}
              className="btn-secondary"
            >
              Reinitialiser
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Reference
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Client
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Date evenement
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Livraison / Retour
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Statut
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Montant
                </th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-dark-400">
                    Chargement...
                  </td>
                </tr>
              ) : reservations.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-dark-400">
                    Aucune reservation trouvee
                  </td>
                </tr>
              ) : (
                reservations.map((reservation) => (
                  <tr
                    key={reservation.id}
                    className="border-b border-dark-700 hover:bg-dark-800/50"
                  >
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm text-primary-400">
                        {reservation.reference}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm">
                        Client #{reservation.customer_id}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm">
                        {formatDate(reservation.event_date)}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-sm">
                        <div>{formatDate(reservation.delivery_date)}</div>
                        <div className="text-dark-500">{formatDate(reservation.return_date)}</div>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'inline-flex items-center px-2 py-1 rounded text-xs',
                          STATUS_COLORS[reservation.status]
                        )}
                      >
                        {STATUS_LABELS[reservation.status]}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-medium">
                        {Number(reservation.total_amount_euros).toFixed(2)} EUR
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-2">
                        <div className="relative">
                          <button
                            onClick={() =>
                              setOpenMenuId(
                                openMenuId === reservation.id ? null : reservation.id
                              )
                            }
                            className="p-1 hover:bg-dark-700 rounded"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>

                          {openMenuId === reservation.id && (
                            <>
                              <div
                                className="fixed inset-0 z-10"
                                onClick={() => setOpenMenuId(null)}
                              />
                              <div className="absolute right-0 mt-2 w-48 bg-dark-800 border border-dark-700 rounded-lg shadow-lg z-20">
                                <button
                                  onClick={() =>
                                    handleOpenModal('details', reservation)
                                  }
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                                >
                                  <Eye className="w-4 h-4" />
                                  Voir details
                                </button>
                                {reservation.status === 'draft' && (
                                  <>
                                    <button
                                      onClick={() =>
                                        handleOpenModal('edit', reservation)
                                      }
                                      className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2"
                                    >
                                      <CalendarCheck className="w-4 h-4" />
                                      Modifier
                                    </button>
                                    <button
                                      onClick={() => {
                                        setOpenMenuId(null)
                                        confirmMutation.mutate(reservation.id)
                                      }}
                                      className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 text-blue-400"
                                    >
                                      <Check className="w-4 h-4" />
                                      Confirmer
                                    </button>
                                  </>
                                )}
                                {(reservation.status === 'draft' || reservation.status === 'confirmed') && (
                                  <button
                                    onClick={() => {
                                      setOpenMenuId(null)
                                      cancelMutation.mutate(reservation.id)
                                    }}
                                    className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 text-red-500 last:rounded-b-lg"
                                  >
                                    <XCircle className="w-4 h-4" />
                                    Annuler
                                  </button>
                                )}
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-dark-700">
            <div className="text-sm text-dark-400">
              Page {page} sur {totalPages}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <ReservationFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        reservation={modal.data}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />

      <ReservationDetailsModal
        isOpen={modal.isOpen('details')}
        onClose={modal.close}
        reservationId={modal.data?.id}
      />
    </div>
  )
}
