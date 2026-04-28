import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useMovementsList, useCompleteMovement } from '@/api/queries'
import { ActionError } from '@shared/components/ui'
import { useMultiModal } from '@/hooks/useModal'
import { MovementFormModal, MovementDeleteModal, MovementDetailModal, ReturnCheckModal } from './components'
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
  ClipboardCheck,
  X,
  Calendar,
} from 'lucide-react'
import { cn, formatDate } from '@/lib/utils'
import { parseISO, format as fmtIso } from 'date-fns'
import { SwipeActions } from '@shared/components/ui'
import { DateRangePicker } from '@shared/components/ui'
import type { SwipeAction } from '@shared/components/ui/SwipeActions'
import {
  MOVEMENT_STATUS_LABELS as STATUS_LABELS,
  MOVEMENT_STATUS_COLORS as STATUS_COLORS,
  MOVEMENT_TYPE_LABELS as TYPE_LABELS,
  PAGE_SIZE_DEFAULT,
} from '@/lib/constants'

type ModalType = 'create' | 'edit' | 'details' | 'delete'

const TYPE_ICONS: Record<MovementType, typeof ArrowUpFromLine> = {
  departure: ArrowUpFromLine,
  return: ArrowDownToLine,
}

const BORDER_COLORS: Record<MovementType, string> = {
  departure: 'border-l-orange-500',
  return: 'border-l-blue-500',
}

function ReturnBadge({ status }: { status: MovementStatus }) {
  if (status === 'completed') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/10 text-green-400">
        <Check className="w-3 h-3" />
        Retourné
      </span>
    )
  }
  if (status === 'late') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-400">
        Retour en retard
      </span>
    )
  }
  return null
}

function CardSkeleton() {
  return (
    <div className="rounded-xl border border-dark-600 border-l-4 border-l-dark-600 bg-dark-900 p-4 animate-pulse space-y-3">
      <div className="flex items-center gap-2">
        <div className="h-4 skel rounded w-12" />
        <div className="h-4 skel rounded w-4" />
        <div className="h-4 skel rounded w-20" />
        <div className="h-5 skel rounded w-16" />
      </div>
      <div className="flex gap-4">
        <div className="h-3 skel rounded w-28" />
        <div className="h-3 skel rounded w-24" />
      </div>
      <div className="h-3 skel rounded w-40" />
    </div>
  )
}

export default function MovementsPage() {
  const {
    page,
    type: typeFilter,
    status: statusFilter,
    reservation: reservationFilter,
    date_from: dateFrom,
    date_to: dateTo,
  } = useSearch({ strict: false }) as {
    page: number
    type: string
    status: string
    reservation: string
    date_from: string
    date_to: string
  }
  const navigate = useNavigate({ from: '/stock/movements/' })
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)

  const modal = useMultiModal<InventoryMovementListItem>()
  const [actionError, setActionError] = useState<string | null>(null)
  const [returnCheckOpen, setReturnCheckOpen] = useState(false)

  const setPage = (p: number) =>
    navigate({ search: (prev) => ({ ...prev, page: p }) })
  const setTypeFilter = (v: string) =>
    navigate({ search: (prev) => ({ ...prev, type: v, page: 1 }) })
  const setStatusFilter = (v: string) =>
    navigate({ search: (prev) => ({ ...prev, status: v, page: 1 }) })
  const setReservationFilter = (v: string) =>
    navigate({ search: (prev) => ({ ...prev, reservation: v, page: 1 }) })
  const setDateFrom = (v: string) =>
    navigate({ search: (prev) => ({ ...prev, date_from: v, page: 1 }) })
  const setDateTo = (v: string) =>
    navigate({ search: (prev) => ({ ...prev, date_to: v, page: 1 }) })
  const resetFilters = () =>
    navigate({
      search: { page: 1, type: '', status: '', reservation: '', date_from: '', date_to: '' },
    })

  const hasActiveFilters = !!(typeFilter || statusFilter || reservationFilter || dateFrom || dateTo)

  const { data, isLoading, error: queryError, refetch } = useMovementsList({
    skip: ((page || 1) - 1) * PAGE_SIZE_DEFAULT,
    limit: PAGE_SIZE_DEFAULT,
    movement_type: (typeFilter as MovementType) || undefined,
    status: (statusFilter as MovementStatus) || undefined,
    reservation_id: reservationFilter ? Number(reservationFilter) : undefined,
    start_date: dateFrom || undefined,
    end_date: dateTo || undefined,
  })

  const completeMutation = useCompleteMovement()

  const movements = data?.items || []
  const totalPages = Math.ceil((data?.total ?? 0) / PAGE_SIZE_DEFAULT) || 1

  const handleOpenModal = (type: ModalType, movement?: InventoryMovementListItem) => {
    setOpenMenuId(null)
    modal.open(type, movement as InventoryMovementListItem)
  }

  const handleComplete = (movementId: number) => {
    setOpenMenuId(null)
    completeMutation.mutate(movementId, {
      onSuccess: () => setActionError(null),
      onError: (err) =>
        setActionError(normalizeError(err).message || 'Erreur lors de la completion'),
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Mouvements de stock" subtitle="Gérez les départs et retours de matériel" />
        <div className="flex gap-2">
          <button
            onClick={() => setReturnCheckOpen(true)}
            className="btn-secondary flex items-center gap-2"
          >
            <ClipboardCheck className="w-4 h-4" />
            <span className="hidden sm:inline">Vérifier retours</span>
          </button>
          <button
            onClick={() => handleOpenModal('create')}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Nouveau mouvement</span>
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="rounded-xl border border-dark-600 bg-dark-900 p-3 sm:p-4">
        <div className="flex gap-2 sm:gap-3 flex-wrap items-center">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="input text-sm flex-1 sm:flex-none sm:w-40"
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
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input text-sm flex-1 sm:flex-none sm:w-44"
          >
            <option value="">Tous les statuts</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <input
            type="number"
            value={reservationFilter}
            onChange={(e) => setReservationFilter(e.target.value)}
            placeholder="Rés. #..."
            className="input text-sm w-24 flex-none"
            min="1"
          />

          <DateRangePicker
            startDate={dateFrom ? parseISO(dateFrom) : null}
            endDate={dateTo ? parseISO(dateTo) : null}
            onChange={({ start, end }) => {
              setDateFrom(start ? fmtIso(start, 'yyyy-MM-dd') : '')
              setDateTo(end ? fmtIso(end, 'yyyy-MM-dd') : '')
            }}
            className="flex-none"
          />

          {hasActiveFilters && (
            <button
              onClick={resetFilters}
              className="btn-secondary text-sm flex items-center gap-1.5"
            >
              <X className="w-3.5 h-3.5" />
              Réinitialiser
            </button>
          )}
        </div>
      </div>

      <ActionError message={actionError} onDismiss={() => setActionError(null)} />

      {/* Cards list */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      ) : queryError ? (
        <div className="rounded-xl border border-dark-600 bg-dark-900 text-center py-12">
          <p className="text-red-400 mb-4">Erreur lors du chargement des mouvements.</p>
          <button onClick={() => refetch()} className="btn-secondary text-sm">
            Réessayer
          </button>
        </div>
      ) : movements.length === 0 ? (
        <div className="rounded-xl border border-dark-600 bg-dark-900 text-center py-12 text-dark-400">
          <Truck className="w-10 h-10 mx-auto mb-2 text-dark-600" />
          Aucun mouvement trouvé
        </div>
      ) : (
        <div className="space-y-3">
          {movements.map((movement) => (
            <MovementCard
              key={movement.id}
              movement={movement}
              openMenuId={openMenuId}
              onToggleMenu={(id) => setOpenMenuId(openMenuId === id ? null : id)}
              onCloseMenu={() => setOpenMenuId(null)}
              onOpenModal={handleOpenModal}
              onComplete={handleComplete}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between rounded-xl border border-dark-600 bg-dark-900 px-4 py-3">
          <div className="text-sm text-dark-400">
            Page {page || 1} sur {totalPages} ({data?.total || 0} résultats)
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(1, (page || 1) - 1))}
              disabled={(page || 1) === 1}
              className="btn-secondary p-2 min-h-[44px] min-w-[44px] flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages, (page || 1) + 1))}
              disabled={(page || 1) === totalPages}
              className="btn-secondary p-2 min-h-[44px] min-w-[44px] flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

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

      <ReturnCheckModal
        isOpen={returnCheckOpen}
        onClose={() => setReturnCheckOpen(false)}
      />
    </div>
  )
}

/* ── Movement Card ──────────────────────────────────────────────── */

function MovementCard({
  movement,
  openMenuId,
  onToggleMenu,
  onCloseMenu,
  onOpenModal,
  onComplete,
}: {
  movement: InventoryMovementListItem
  openMenuId: number | null
  onToggleMenu: (id: number) => void
  onCloseMenu: () => void
  onOpenModal: (type: ModalType, m?: InventoryMovementListItem) => void
  onComplete: (id: number) => void
}) {
  const TypeIcon = TYPE_ICONS[movement.movement_type]
  const canEdit = movement.status === 'scheduled'
  const canDelete = movement.status === 'scheduled' || movement.status === 'in_transit'
  const canComplete =
    (movement.status === 'scheduled' || movement.status === 'in_transit') &&
    !movement.reservation_id

  const leftSwipe: SwipeAction[] = [
    ...(canDelete ? [{ icon: <Trash2 className="w-4 h-4" />, label: 'Supprimer', color: 'bg-red-600', onClick: () => onOpenModal('delete', movement) }] : []),
  ]

  const rightSwipe: SwipeAction[] = [
    ...(canComplete ? [{ icon: <Check className="w-4 h-4" />, label: 'Compléter', color: 'bg-emerald-600', onClick: () => onComplete(movement.id) }] : []),
    ...(canEdit ? [{ icon: <Pencil className="w-4 h-4" />, label: 'Modifier', color: 'bg-primary-600', onClick: () => onOpenModal('edit', movement) }] : []),
  ]

  return (
    <SwipeActions leftActions={leftSwipe} rightActions={rightSwipe}>
      <div
        className={cn(
          'rounded-xl border border-dark-600 border-l-4 bg-dark-900 p-4 transition-colors hover:bg-dark-600/50',
          BORDER_COLORS[movement.movement_type],
        )}
      >
        {/* Row 1: ID + Type + Status + Return badge + Menu */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-xs text-primary-400 shrink-0">
            #{movement.id}
          </span>

          <TypeIcon
            className={cn(
              'w-4 h-4 shrink-0',
              movement.movement_type === 'departure' ? 'text-orange-400' : 'text-blue-400',
            )}
          />
          <span className="text-sm font-medium">
            {TYPE_LABELS[movement.movement_type]}
          </span>

          <span
            className={cn(
              'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
              STATUS_COLORS[movement.status],
            )}
          >
            {STATUS_LABELS[movement.status]}
          </span>

          {movement.movement_type === 'return' && (
            <ReturnBadge status={movement.status} />
          )}

          {/* Spacer + dropdown menu */}
          <div className="ml-auto relative shrink-0">
            <button
              onClick={() => onToggleMenu(movement.id)}
              className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-dark-600 rounded-lg"
            >
              <MoreVertical className="w-4 h-4" />
            </button>
            {openMenuId === movement.id && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  aria-hidden="true"
                  onClick={onCloseMenu}
                />
                <div className="absolute right-0 mt-1 w-48 dropdown-menu z-20">
                  <button
                    onClick={() => onOpenModal('details', movement)}
                    className="w-full px-4 py-2 text-left hover:bg-dark-600 flex items-center gap-2 first:rounded-t-lg"
                  >
                    <Eye className="w-4 h-4" />
                    Voir détails
                  </button>
                  {canEdit && (
                    <button
                      onClick={() => onOpenModal('edit', movement)}
                      className="w-full px-4 py-2 text-left hover:bg-dark-600 flex items-center gap-2"
                    >
                      <Pencil className="w-4 h-4" />
                      Modifier
                    </button>
                  )}
                  {canComplete && (
                    <button
                      onClick={() => onComplete(movement.id)}
                      className="w-full px-4 py-2 text-left hover:bg-dark-600 flex items-center gap-2 text-green-400"
                    >
                      <Check className="w-4 h-4" />
                      Compléter
                    </button>
                  )}
                  {canDelete && (
                    <button
                      onClick={() => onOpenModal('delete', movement)}
                      className="w-full px-4 py-2 text-left hover:bg-dark-600 flex items-center gap-2 text-red-500 last:rounded-b-lg"
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

        {/* Row 2: Dates */}
        <div className="flex items-center gap-4 mt-2 text-sm text-dark-300">
          <span className="flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-dark-500" />
            {formatDate(movement.scheduled_date?.split('T')[0])}
          </span>
          {movement.actual_date && (
            <span className="flex items-center gap-1.5 text-dark-400">
              <Check className="w-3.5 h-3.5 text-green-500" />
              {formatDate(movement.actual_date)}
            </span>
          )}
        </div>

        {/* Row 3: Products + Reservation */}
        <div className="flex items-center gap-2 mt-2 text-sm flex-wrap">
          {movement.product_names.length > 0 ? (
            <span className="text-dark-200">
              {movement.product_names.slice(0, 2).join(', ')}
              {movement.product_names.length > 2 && (
                <span className="text-dark-400">
                  {' '}
                  +{movement.product_names.length - 2}
                </span>
              )}
            </span>
          ) : (
            <span className="text-dark-400">
              {movement.items_count} article{movement.items_count !== 1 ? 's' : ''}
            </span>
          )}
          {movement.reservation_id && (
            <span className="text-primary-400 text-xs font-medium">
              Rés. #{movement.reservation_id}
            </span>
          )}
        </div>
      </div>
    </SwipeActions>
  )
}
