import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { inventoryApi } from '@/api/inventory'
import { useMultiModal } from '@/hooks/useModal'
import { MovementFormModal, MovementDeleteModal } from './components'
import type { InventoryMovementListItem, MovementType, MovementStatus, DeliveryMethod } from '@/types/inventory'
import {
  TruckIcon,
  Plus,
  Edit,
  Trash2,
  CheckCircle,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDate } from '@/lib/utils'

type ModalType = 'create' | 'edit' | 'delete'

const MOVEMENT_TYPE_LABELS: Record<MovementType, string> = {
  departure: 'Départ',
  return: 'Retour',
}

const STATUS_LABELS: Record<MovementStatus, string> = {
  scheduled: 'Programmé',
  in_transit: 'En transit',
  completed: 'Terminé',
  late: 'En retard',
  cancelled: 'Annulé',
}

const DELIVERY_METHOD_LABELS: Record<DeliveryMethod, string> = {
  delivery: 'Livraison',
  pickup: 'Enlèvement',
  shipping: 'Expédition',
}

export default function MovementsPage() {
  const [page, setPage] = useState(1)
  const [typeFilter, setTypeFilter] = useState<MovementType | ''>('')
  const [statusFilter, setStatusFilter] = useState<MovementStatus | ''>('')
  const [activeTab, setActiveTab] = useState<'all' | 'late' | 'inspections'>('all')
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)

  const modal = useMultiModal<InventoryMovementListItem>()

  const { data, isLoading } = useQuery<InventoryMovementListItem[]>({
    queryKey: ['inventory-movements', page, typeFilter, statusFilter, activeTab],
    queryFn: async () => {
      if (activeTab === 'late') return inventoryApi.getLateMovements()
      if (activeTab === 'inspections') return inventoryApi.getPendingInspections()

      const result = await inventoryApi.getMovements({
        page,
        page_size: 20,
        movement_type: typeFilter || undefined,
        status: statusFilter || undefined,
      })
      return result.items
    },
  })

  const movements = data || []

  const handleOpenModal = (type: ModalType, movement?: InventoryMovementListItem) => {
    setOpenMenuId(null)
    modal.open(type, movement as any)
  }

  const getStatusColor = (status: MovementStatus) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500/10 text-green-500'
      case 'in_transit':
        return 'bg-blue-500/10 text-blue-500'
      case 'late':
        return 'bg-red-500/10 text-red-500'
      case 'cancelled':
        return 'bg-dark-700 text-dark-400'
      default:
        return 'bg-yellow-500/10 text-yellow-500'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Mouvements d'inventaire</h1>
          <p className="text-dark-400 mt-1">Gérez les départs et retours de matériel</p>
        </div>
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Nouveau mouvement
        </button>
      </div>

      {/* Tabs */}
      <div className="card p-0">
        <div className="flex border-b border-dark-700">
          <button
            onClick={() => setActiveTab('all')}
            className={cn(
              'px-6 py-3 font-medium text-sm border-b-2 transition-colors',
              activeTab === 'all'
                ? 'border-primary-500 text-primary-500'
                : 'border-transparent text-dark-400 hover:text-dark-200'
            )}
          >
            Tous les mouvements
          </button>
          <button
            onClick={() => setActiveTab('late')}
            className={cn(
              'px-6 py-3 font-medium text-sm border-b-2 transition-colors flex items-center gap-2',
              activeTab === 'late'
                ? 'border-red-500 text-red-500'
                : 'border-transparent text-dark-400 hover:text-dark-200'
            )}
          >
            <AlertCircle className="w-4 h-4" />
            En retard
          </button>
          <button
            onClick={() => setActiveTab('inspections')}
            className={cn(
              'px-6 py-3 font-medium text-sm border-b-2 transition-colors flex items-center gap-2',
              activeTab === 'inspections'
                ? 'border-yellow-500 text-yellow-500'
                : 'border-transparent text-dark-400 hover:text-dark-200'
            )}
          >
            <CheckCircle className="w-4 h-4" />
            Inspections en attente
          </button>
        </div>
      </div>

      {/* Filters */}
      {activeTab === 'all' && (
        <div className="card">
          <div className="flex gap-4">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as MovementType | '')}
              className="input"
            >
              <option value="">Tous les types</option>
              <option value="departure">Départs</option>
              <option value="return">Retours</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as MovementStatus | '')}
              className="input"
            >
              <option value="">Tous les statuts</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>

            {(typeFilter || statusFilter) && (
              <button
                onClick={() => {
                  setTypeFilter('')
                  setStatusFilter('')
                }}
                className="btn-secondary"
              >
                Réinitialiser
              </button>
            )}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Type</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Date prévue</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Livraison</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Articles</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Statut</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-dark-400">Chargement...</td>
                </tr>
              ) : movements.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-dark-400">Aucun mouvement trouvé</td>
                </tr>
              ) : (
                movements.map((movement) => (
                  <tr key={movement.id} className="border-b border-dark-700 hover:bg-dark-800/50">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <TruckIcon className={cn(
                          'w-4 h-4',
                          movement.movement_type === 'departure' ? 'text-blue-500' : 'text-green-500'
                        )} />
                        <span>{MOVEMENT_TYPE_LABELS[movement.movement_type]}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm">{formatDate(movement.scheduled_date)}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm">
                        {movement.delivery_method ? DELIVERY_METHOD_LABELS[movement.delivery_method as keyof typeof DELIVERY_METHOD_LABELS] : '-'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm">{movement.items_count || 0}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={cn('inline-flex items-center px-2 py-1 rounded text-xs', getStatusColor(movement.status))}>
                        {STATUS_LABELS[movement.status]}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-2">
                        <div className="relative">
                          <button
                            onClick={() => setOpenMenuId(openMenuId === movement.id ? null : movement.id)}
                            className="p-1 hover:bg-dark-700 rounded"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>

                          {openMenuId === movement.id && (
                            <>
                              <div className="fixed inset-0 z-10" onClick={() => setOpenMenuId(null)} />
                              <div className="absolute right-0 mt-2 w-48 bg-dark-800 border border-dark-700 rounded-lg shadow-lg z-20">
                                <button
                                  onClick={() => handleOpenModal('edit', movement)}
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                                >
                                  <Edit className="w-4 h-4" />
                                  Modifier
                                </button>
                                <button
                                  onClick={() => handleOpenModal('delete', movement)}
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
      </div>

      {/* Modals */}
      <MovementFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        movement={modal.data}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />

      <MovementDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        movement={modal.data}
      />
    </div>
  )
}
