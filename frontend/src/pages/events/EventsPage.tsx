import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { eventsApi } from '@/api/events'
import { useMultiModal } from '@/hooks/useModal'
import { EventFormModal, EventDeleteModal, EventDetailsModal } from './components'
import type { EventListItem, EventStatus, EventType } from '@/types/event'
import {
  Calendar,
  Plus,
  Edit,
  Trash2,
  Eye,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDate } from '@/lib/utils'

type ModalType = 'create' | 'edit' | 'delete' | 'details'

const EVENT_TYPE_LABELS: Record<EventType, string> = {
  wedding: 'Mariage',
  baptism: 'Baptême',
  birthday: 'Anniversaire',
  seminar: 'Séminaire',
  other: 'Autre',
}

const EVENT_STATUS_LABELS: Record<EventStatus, string> = {
  pending: 'En attente',
  confirmed: 'Confirmé',
  in_progress: 'En cours',
  completed: 'Terminé',
  cancelled: 'Annulé',
}

const PAYMENT_STATUS_LABELS = {
  unpaid: 'Non payé',
  partial: 'Partiel',
  paid: 'Payé',
  refunded: 'Remboursé',
}

export default function EventsPage() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<EventStatus | ''>('')
  const [typeFilter, setTypeFilter] = useState<EventType | ''>('')
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)

  const modal = useMultiModal<EventListItem>()

  const { data, isLoading } = useQuery({
    queryKey: ['events', page, statusFilter, typeFilter],
    queryFn: () =>
      eventsApi.getEvents({
        page,
        page_size: 20,
        status: statusFilter || undefined,
        event_type: typeFilter || undefined,
      }),
  })

  const { data: stats } = useQuery({
    queryKey: ['events-stats'],
    queryFn: () => eventsApi.getStatistics(),
  })

  const events = data?.items || []
  const totalPages = data?.total_pages || 1

  const handleOpenModal = (type: ModalType, event?: EventListItem) => {
    setOpenMenuId(null)
    modal.open(type, event as any)
  }

  const getStatusColor = (status: EventStatus) => {
    switch (status) {
      case 'confirmed':
        return 'bg-blue-500/10 text-blue-500'
      case 'in_progress':
        return 'bg-yellow-500/10 text-yellow-500'
      case 'completed':
        return 'bg-green-500/10 text-green-500'
      case 'cancelled':
        return 'bg-red-500/10 text-red-500'
      default:
        return 'bg-dark-700 text-dark-400'
    }
  }

  const getPaymentStatusColor = (status: string) => {
    switch (status) {
      case 'paid':
        return 'text-green-500'
      case 'partial':
        return 'text-yellow-500'
      case 'refunded':
        return 'text-blue-500'
      default:
        return 'text-red-500'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Événements & Ventes</h1>
          <p className="text-dark-400 mt-1">
            Gérez les événements clients et locations
          </p>
        </div>
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Nouvel événement
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Total événements</p>
                <p className="text-2xl font-bold mt-1">{stats.total_events}</p>
              </div>
              <Calendar className="w-8 h-8 text-primary-500" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Confirmés</p>
                <p className="text-2xl font-bold mt-1 text-blue-500">
                  {stats.confirmed}
                </p>
              </div>
              <TrendingUp className="w-8 h-8 text-blue-500" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">En cours</p>
                <p className="text-2xl font-bold mt-1 text-yellow-500">
                  {stats.in_progress}
                </p>
              </div>
              <TrendingUp className="w-8 h-8 text-yellow-500" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Revenu total</p>
                <p className="text-2xl font-bold mt-1 text-green-500">
                  {Number(stats.total_revenue).toFixed(0)} €
                </p>
              </div>
              <TrendingUp className="w-8 h-8 text-green-500" />
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card">
        <div className="flex gap-4 flex-wrap">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as EventType | '')}
            className="input"
          >
            <option value="">Tous les types</option>
            {Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <select
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(e.target.value as EventStatus | '')
            }
            className="input"
          >
            <option value="">Tous les statuts</option>
            {Object.entries(EVENT_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          {(statusFilter || typeFilter) && (
            <button
              onClick={() => {
                setStatusFilter('')
                setTypeFilter('')
              }}
              className="btn-secondary"
            >
              Réinitialiser
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
                  Client
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Type
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Date événement
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Statut
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Paiement
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Total
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
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-dark-400">
                    Aucun événement trouvé
                  </td>
                </tr>
              ) : (
                events.map((event) => (
                  <tr
                    key={event.id}
                    className="border-b border-dark-700 hover:bg-dark-800/50"
                  >
                    <td className="py-3 px-4">
                      <div>
                        <div className="font-medium">{event.customer_name}</div>
                        {event.customer_email && (
                          <div className="text-sm text-dark-400">
                            {event.customer_email}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm">
                        {EVENT_TYPE_LABELS[event.event_type]}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm">
                        {formatDate(event.event_date)}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'inline-flex items-center px-2 py-1 rounded text-xs',
                          getStatusColor(event.status)
                        )}
                      >
                        {EVENT_STATUS_LABELS[event.status]}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'text-sm font-medium',
                          getPaymentStatusColor(event.payment_status)
                        )}
                      >
                        {PAYMENT_STATUS_LABELS[event.payment_status as keyof typeof PAYMENT_STATUS_LABELS]}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-medium">
                        {Number(event.total_amount).toFixed(2)} €
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-2">
                        <div className="relative">
                          <button
                            onClick={() =>
                              setOpenMenuId(
                                openMenuId === event.id ? null : event.id
                              )
                            }
                            className="p-1 hover:bg-dark-700 rounded"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>

                          {openMenuId === event.id && (
                            <>
                              <div
                                className="fixed inset-0 z-10"
                                onClick={() => setOpenMenuId(null)}
                              />
                              <div className="absolute right-0 mt-2 w-48 bg-dark-800 border border-dark-700 rounded-lg shadow-lg z-20">
                                <button
                                  onClick={() =>
                                    handleOpenModal('details', event)
                                  }
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                                >
                                  <Eye className="w-4 h-4" />
                                  Voir détails
                                </button>
                                <button
                                  onClick={() => handleOpenModal('edit', event)}
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2"
                                >
                                  <Edit className="w-4 h-4" />
                                  Modifier
                                </button>
                                <button
                                  onClick={() =>
                                    handleOpenModal('delete', event)
                                  }
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 text-red-500 last:rounded-b-lg"
                                >
                                  <Trash2 className="w-4 h-4" />
                                  Supprimer
                                </button>
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
      <EventFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        event={modal.data}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />

      <EventDetailsModal
        isOpen={modal.isOpen('details')}
        onClose={modal.close}
        eventId={modal.data?.id}
      />

      <EventDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        event={modal.data}
      />
    </div>
  )
}
