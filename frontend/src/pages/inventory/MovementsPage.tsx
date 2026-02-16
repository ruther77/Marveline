import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { inventoryApi } from '@/api/inventory'
import { useMultiModal } from '@/hooks/useModal'
import { MovementFormModal, MovementDeleteModal, MovementDetailModal } from './components'
import type {
  InventoryMovementListItem,
  MovementType,
  MovementStatus,
} from '@/types/inventory'
import {
  Truck,
  Plus,
  Eye,
  Pencil,
  Check,
  Trash2,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  ArrowDownToLine,
  ArrowUpFromLine,
} from 'lucide-react'
import { cn, formatDate } from '@/lib/utils'

type ModalType = 'create' | 'edit' | 'details' | 'delete'

const STATUS_LABELS: Record<MovementStatus, string> = {
  scheduled: 'Planifie',
  in_transit: 'En transit',
  completed: 'Termine',
  late: 'En retard',
  cancelled: 'Annule',
}

const STATUS_COLORS: Record<MovementStatus, string> = {
  scheduled: 'bg-blue-500/10 text-blue-500',
  in_transit: 'bg-orange-500/10 text-orange-500',
  completed: 'bg-green-500/10 text-green-500',
  late: 'bg-red-500/10 text-red-500',
  cancelled: 'bg-dark-700 text-dark-300',
}

const TYPE_LABELS: Record<MovementType, string> = {
  departure: 'Depart',
  return: 'Retour',
}

const TYPE_ICONS: Record<MovementType, typeof ArrowUpFromLine> = {
  departure: ArrowUpFromLine,
  return: ArrowDownToLine,
}

export default function MovementsPage() {
  const [page, setPage] = useState(1)
  const [typeFilter, setTypeFilter] = useState<MovementType | ''>('')
  const [statusFilter, setStatusFilter] = useState<MovementStatus | ''>('')
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const queryClient = useQueryClient()

  const modal = useMultiModal<InventoryMovementListItem>()

  const { data, isLoading } = useQuery({
    queryKey: ['inventory-movements', page, typeFilter, statusFilter],
    queryFn: () =>
      inventoryApi.getMovements({
        page,
        page_size: 20,
        movement_type: typeFilter || undefined,
        status: statusFilter || undefined,
      }),
  })

  const completeMutation = useMutation({
    mutationFn: (id: number) => inventoryApi.completeMovement(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory-movements'] })
    },
  })

  const movements = data?.items || []
  const totalPages = data?.total_pages || 1

  const handleOpenModal = (type: ModalType, movement?: InventoryMovementListItem) => {
    setOpenMenuId(null)
    modal.open(type, movement as InventoryMovementListItem)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Mouvements de stock</h1>
          <p className="text-dark-400 mt-1">
            Gerez les departs et retours de materiel
          </p>
        </div>
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Nouveau mouvement
        </button>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex gap-4 flex-wrap">
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value as MovementType | '')
              setPage(1)
            }}
            className="input"
          >
            <option value="">Tous les types</option>
            {Object.entries(TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as MovementStatus | '')
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

          {(typeFilter || statusFilter) && (
            <button
              onClick={() => {
                setTypeFilter('')
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
                  #
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Type
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Date prevue
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Date effective
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Statut
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Articles
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
              ) : movements.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-dark-400">
                    <Truck className="w-10 h-10 mx-auto mb-2 text-dark-600" />
                    Aucun mouvement trouve
                  </td>
                </tr>
              ) : (
                movements.map((movement) => {
                  const TypeIcon = TYPE_ICONS[movement.movement_type]
                  return (
                    <tr
                      key={movement.id}
                      className="border-b border-dark-700 hover:bg-dark-800/50"
                    >
                      <td className="py-3 px-4">
                        <span className="font-mono text-sm text-primary-400">
                          #{movement.id}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <TypeIcon className={cn(
                            'w-4 h-4',
                            movement.movement_type === 'departure'
                              ? 'text-orange-400'
                              : 'text-blue-400'
                          )} />
                          <span className="text-sm">
                            {TYPE_LABELS[movement.movement_type]}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm">
                          {formatDate(movement.scheduled_date)}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-dark-400">
                          {movement.actual_date
                            ? formatDate(movement.actual_date)
                            : '-'}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={cn(
                            'inline-flex items-center px-2 py-1 rounded text-xs',
                            STATUS_COLORS[movement.status]
                          )}
                        >
                          {STATUS_LABELS[movement.status]}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-dark-300">
                          {movement.items_count} article{movement.items_count !== 1 ? 's' : ''}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center justify-end">
                          <div className="relative">
                            <button
                              onClick={() =>
                                setOpenMenuId(
                                  openMenuId === movement.id ? null : movement.id
                                )
                              }
                              className="p-1 hover:bg-dark-700 rounded"
                            >
                              <MoreVertical className="w-4 h-4" />
                            </button>

                            {openMenuId === movement.id && (
                              <>
                                <div
                                  className="fixed inset-0 z-10"
                                  onClick={() => setOpenMenuId(null)}
                                />
                                <div className="absolute right-0 mt-2 w-48 bg-dark-800 border border-dark-700 rounded-lg shadow-lg z-20">
                                  <button
                                    onClick={() =>
                                      handleOpenModal('details', movement)
                                    }
                                    className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                                  >
                                    <Eye className="w-4 h-4" />
                                    Voir details
                                  </button>
                                  {movement.status === 'scheduled' && (
                                    <>
                                      <button
                                        onClick={() =>
                                          handleOpenModal('edit', movement)
                                        }
                                        className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2"
                                      >
                                        <Pencil className="w-4 h-4" />
                                        Modifier
                                      </button>
                                      <button
                                        onClick={() => {
                                          setOpenMenuId(null)
                                          completeMutation.mutate(movement.id)
                                        }}
                                        className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 text-green-400"
                                      >
                                        <Check className="w-4 h-4" />
                                        Completer
                                      </button>
                                    </>
                                  )}
                                  {movement.status === 'in_transit' && (
                                    <button
                                      onClick={() => {
                                        setOpenMenuId(null)
                                        completeMutation.mutate(movement.id)
                                      }}
                                      className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 text-green-400"
                                    >
                                      <Check className="w-4 h-4" />
                                      Completer
                                    </button>
                                  )}
                                  {(movement.status === 'scheduled' || movement.status === 'in_transit') && (
                                    <button
                                      onClick={() =>
                                        handleOpenModal('delete', movement)
                                      }
                                      className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 text-red-500 last:rounded-b-lg"
                                    >
                                      <Trash2 className="w-4 h-4" />
                                      Supprimer
                                    </button>
                                  )}
                                </div>
                              </>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-dark-700">
            <div className="text-sm text-dark-400">
              Page {page} sur {totalPages} ({data?.total || 0} resultats)
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
      <MovementFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        movement={modal.data}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />

      <MovementDetailModal
        isOpen={modal.isOpen('details')}
        onClose={modal.close}
        movementId={modal.data?.id}
      />

      <MovementDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        movement={modal.data}
      />
    </div>
  )
}
