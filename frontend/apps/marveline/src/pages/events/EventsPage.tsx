import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useHasScope } from '@/hooks/useHasScope'
import { useReservationsList, useReservationsStats, useConfirmReservation, useCancelReservation, useDeliverReservation, useCompleteReservation } from '@/api/queries'
import { ErrorState, NoData, NoSearchResults } from '@shared/components/ui/EmptyState'
import { normalizeError } from '@shared/errors/normalizer'

import { useMultiModal } from '@/hooks/useModal'
import { ReservationFormModal } from './components'
import type { ReservationList, ReservationStatus } from '@/types/reservation'
import {
  CalendarCheck, Plus, Check, XCircle, ChevronLeft, ChevronRight,
  MapPin, Users, Truck, LayoutList, Kanban, CreditCard, Clock, Pencil,
  PackageCheck, RotateCcw, UserCheck,
} from 'lucide-react'
import { cn, formatDate, formatCents } from '@/lib/utils'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { EVENT_TYPE_LABELS, PAGE_SIZE_DEFAULT } from '@/lib/constants'
import { DomainStatusBadge, ActionError, SwipeActions, KanbanBoard, PaymentProgressBar } from '@shared/components/ui'
import type { KanbanColumn } from '@shared/components/ui/KanbanBoard'
import type { SwipeAction } from '@shared/components/ui/SwipeActions'

// ── Status config ──────────────────────────────────────────────────────────
const STATUS_CONFIG: Record<string, { label: string; dot: string; accent: string; border: string }> = {
  draft:             { label: 'Brouillon',  dot: 'bg-dark-400',   accent: 'text-dark-300',  border: 'border-l-dark-400' },
  confirmed:         { label: 'Confirmée',  dot: 'bg-blue-500',   accent: 'text-blue-400',  border: 'border-l-blue-500' },
  confirmed_risk:    { label: 'Risque',     dot: 'bg-red-500',    accent: 'text-red-400',   border: 'border-l-red-500' },
  pre_check:         { label: 'Pré-check',  dot: 'bg-violet-500', accent: 'text-violet-400', border: 'border-l-violet-500' },
  delivered:         { label: 'Livrée',     dot: 'bg-amber-500',  accent: 'text-amber-400', border: 'border-l-amber-500' },
  extended:          { label: 'Prolongée',  dot: 'bg-orange-500', accent: 'text-orange-400', border: 'border-l-orange-500' },
  returned:          { label: 'Retournée',  dot: 'bg-green-500',  accent: 'text-green-400', border: 'border-l-green-500' },
  returned_dispute:  { label: 'Litige',     dot: 'bg-red-400',    accent: 'text-red-400',   border: 'border-l-red-400' },
  completed:         { label: 'Terminée',   dot: 'bg-emerald-500', accent: 'text-emerald-400', border: 'border-l-emerald-500' },
  cancelled:         { label: 'Annulée',    dot: 'bg-dark-500',   accent: 'text-dark-500',  border: 'border-l-dark-500' },
}

const STATUS_CHIPS: { value: ReservationStatus | ''; label: string; dot?: string }[] = [
  { value: '', label: 'Toutes' },
  ...Object.entries(STATUS_CONFIG).map(([k, v]) => ({ value: k as ReservationStatus, label: v.label, dot: v.dot })),
]

// ── Skeleton ───────────────────────────────────────────────────────────────
function CardSkeleton() {
  return (
    <div className="rounded-xl border border-dark-600 border-l-4 border-l-dark-600 bg-dark-900 p-4 animate-pulse">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-3">
          <div className="flex items-center gap-3">
            <div className="h-4 skel rounded w-24" />
            <div className="h-5 skel rounded-full w-20" />
          </div>
          <div className="h-3 skel rounded w-40" />
          <div className="h-2 skel rounded w-56" />
        </div>
        <div className="space-y-2 text-right">
          <div className="h-5 skel rounded w-20 ml-auto" />
          <div className="h-1.5 skel rounded w-28" />
        </div>
      </div>
    </div>
  )
}

type ModalType = 'create' | 'edit' | 'details'

// ── Reservation Card ───────────────────────────────────────────────────────
function ReservationCard({
  r,
  onNavigate,
  highlight,
}: {
  r: ReservationList
  onNavigate: () => void
  highlight?: boolean
}) {
  const cfg = STATUS_CONFIG[r.status] ?? STATUS_CONFIG.draft
  const paymentLabel =
    r.payment_status === 'paid' ? 'Payé' :
    r.payment_status === 'partial' ? 'Partiel' : 'Impayé'
  const paymentColor =
    r.payment_status === 'paid' ? 'text-green-400 bg-green-500/10' :
    r.payment_status === 'partial' ? 'text-amber-400 bg-amber-500/10' :
    'text-red-400 bg-red-500/10'

  return (
    <button
      type="button"
      onClick={onNavigate}
      className={cn(
        'w-full text-left rounded-xl border border-dark-600 border-l-4 bg-dark-900',
        'hover:bg-dark-600 hover:border-dark-600 transition-all group',
        cfg.border,
        highlight && 'ring-2 ring-primary-500 bg-primary-500/5',
      )}
    >
      <div className="p-4">
        {/* Row 1 : Ref + Status + Amount */}
        <div className="flex items-center justify-between gap-3 mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-mono text-xs font-bold text-primary-400">{r.reference}</span>
            <DomainStatusBadge status={r.status} size="sm" />
          </div>
          <span className="text-base font-bold text-dark-50 tabular-nums shrink-0">
            {formatCents(r.total_amount_cents)}
          </span>
        </div>

        {/* Row 2 : Client + Event type */}
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-sm font-semibold text-dark-100 truncate">
            {r.customer_name || `Client #${r.customer_id}`}
          </span>
          {r.event_type && (
            <span className="shrink-0 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide bg-primary-500/10 text-primary-400">
              {EVENT_TYPE_LABELS[r.event_type] || r.event_type}
            </span>
          )}
        </div>

        {/* Row 3 : Dates + location */}
        <div className="flex items-center gap-3 text-xs text-dark-400 mb-3">
          <span className="flex items-center gap-1">
            <CalendarCheck className="w-3 h-3 text-dark-500" />
            {formatDate(r.event_date)}
          </span>
          <span className="text-dark-600">|</span>
          <span className="flex items-center gap-1">
            <Truck className="w-3 h-3 text-dark-500" />
            {formatDate(r.delivery_date)} → {formatDate(r.return_date)}
          </span>
          {r.event_location && (
            <>
              <span className="text-dark-600">|</span>
              <span className="flex items-center gap-1 truncate">
                <MapPin className="w-3 h-3 text-dark-500 shrink-0" />
                {r.event_location}
              </span>
            </>
          )}
          {r.guest_count && (
            <span className="flex items-center gap-1">
              <Users className="w-3 h-3 text-dark-500" />
              {r.guest_count}
            </span>
          )}
        </div>

        {/* Row 4 : Payment + Deposit badges */}
        <div className="flex items-center gap-2">
          <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold', paymentColor)}>
            <CreditCard className="w-3 h-3" />
            {paymentLabel}
          </span>
          {r.deposit_paid ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold text-green-400 bg-green-500/10">
              <Check className="w-3 h-3" /> Caution
            </span>
          ) : r.deposit_amount_cents > 0 ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold text-amber-400 bg-amber-500/10">
              <Clock className="w-3 h-3" /> Caution
            </span>
          ) : null}
          {/* Spacer + mini payment bar */}
          <div className="flex-1" />
          <div className="w-28 hidden sm:block">
            <PaymentProgressBar paidCents={r.paid_amount_cents ?? 0} totalCents={r.total_amount_cents} size="sm" />
          </div>
        </div>
      </div>
    </button>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────
export default function EventsPage() {
  const navigate = useNavigate({ from: '/reservations/' })
  const { page, status: statusParam, highlight, assigned_to_me } = useSearch({ strict: false }) as { page: number; status: ReservationStatus | ''; highlight?: number; assigned_to_me?: boolean }
  const canWrite = useHasScope('reservations:write')

  const setPage = (p: number) => navigate({ search: (prev) => ({ ...prev, page: p }) })
  const setStatus = (s: ReservationStatus | '') => navigate({ search: (prev) => ({ ...prev, status: s || undefined, page: 1 }) })
  const toggleAssignedToMe = () => navigate({ search: (prev) => ({ ...prev, assigned_to_me: assigned_to_me ? undefined : true, page: 1 }) })

  const [viewMode, setViewMode] = useState<'list' | 'kanban'>('list')
  const modal = useMultiModal<ReservationList>()
  const [actionError, setActionError] = useState<string | null>(null)

  const currentStatus = statusParam || ''

  const { data, isLoading, error, refetch } = useReservationsList({
    skip: (page - 1) * PAGE_SIZE_DEFAULT,
    limit: PAGE_SIZE_DEFAULT,
    status: currentStatus ? (currentStatus as ReservationStatus) : undefined,
    assigned_to_me: assigned_to_me || undefined,
  })
  const confirmMutation = useConfirmReservation()
  const cancelMutation = useCancelReservation()
  const deliverMutation = useDeliverReservation()
  const completeMutation = useCompleteReservation()
  const onErr = (err: unknown) => setActionError(normalizeError(err).message || 'Erreur')
  const { data: statsMap } = useReservationsStats()

  const reservations = data?.items || []
  const totalPages = Math.ceil((data?.total ?? 0) / PAGE_SIZE_DEFAULT) || 1
  const total = data?.total ?? 0

  return (
    <div className="space-y-5">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Réservations" subtitle={total > 0 ? `${total} réservation${total > 1 ? 's' : ''}` : 'Gérez les réservations et locations'} />
        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="hidden sm:flex items-center bg-dark-900 rounded-lg border border-dark-600 p-0.5">
            <button type="button" onClick={() => setViewMode('list')} className={cn('p-2 rounded-md transition-colors', viewMode === 'list' ? 'bg-primary-500/20 text-primary-400' : 'text-dark-400 hover:text-dark-200')} title="Vue liste">
              <LayoutList className="w-4 h-4" />
            </button>
            <button type="button" onClick={() => setViewMode('kanban')} className={cn('p-2 rounded-md transition-colors', viewMode === 'kanban' ? 'bg-primary-500/20 text-primary-400' : 'text-dark-400 hover:text-dark-200')} title="Vue kanban">
              <Kanban className="w-4 h-4" />
            </button>
          </div>
          {canWrite && (
            <Link to="/devis/new" className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" /><span className="hidden sm:inline">Nouveau devis</span>
            </Link>
          )}
        </div>
      </div>

      {/* ── KPI Cards ───────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {([
          { key: 'delivered', label: 'En cours', icon: <Truck className="w-5 h-5" />, value: statsMap?.delivered, bg: 'bg-amber-500/10', ring: 'ring-amber-500/20', text: 'text-amber-400', iconBg: 'bg-amber-500/20' },
          { key: 'confirmed', label: 'Confirmées', icon: <Check className="w-5 h-5" />, value: statsMap?.confirmed, bg: 'bg-blue-500/10', ring: 'ring-blue-500/20', text: 'text-blue-400', iconBg: 'bg-blue-500/20' },
          { key: 'returned', label: 'Retournées', icon: <CalendarCheck className="w-5 h-5" />, value: statsMap?.returned, bg: 'bg-green-500/10', ring: 'ring-green-500/20', text: 'text-green-400', iconBg: 'bg-green-500/20' },
          { key: 'draft', label: 'Brouillons', icon: <Pencil className="w-5 h-5" />, value: statsMap?.draft, bg: 'bg-dark-900', ring: 'ring-dark-600', text: 'text-dark-300', iconBg: 'bg-dark-900' },
        ] as const).map((kpi) => (
          <button
            key={kpi.key}
            type="button"
            onClick={() => setStatus(kpi.key as ReservationStatus)}
            className={cn(
              'rounded-xl p-4 text-left transition-all ring-1',
              kpi.bg, kpi.ring,
              currentStatus === kpi.key && 'ring-2 ring-primary-500 bg-primary-500/5',
            )}
          >
            <div className="flex items-center gap-3">
              <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', kpi.iconBg, kpi.text)}>{kpi.icon}</div>
              <div>
                <p className={cn('text-2xl font-bold tabular-nums', kpi.text)}>{kpi.value ?? '—'}</p>
                <p className="text-[11px] text-dark-400 font-medium">{kpi.label}</p>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* ── Status chips ────────────────────────────────────────── */}
      <div className="overflow-x-auto -mx-4 px-4">
        <div className="flex gap-1.5 pb-1 min-w-max">
          <button
            type="button"
            onClick={toggleAssignedToMe}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all',
              assigned_to_me
                ? 'bg-gold-400 text-dark-900 shadow-lg shadow-gold-400/20'
                : 'bg-dark-900 text-dark-300 hover:bg-dark-600 hover:text-dark-100 ring-1 ring-dark-600',
            )}
          >
            <UserCheck className="w-3.5 h-3.5" />
            Mes réservations
          </button>
          <span className="w-px bg-dark-600 mx-1" />
          {STATUS_CHIPS.map((chip) => (
            <button
              key={chip.value}
              type="button"
              onClick={() => setStatus(chip.value)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all',
                currentStatus === chip.value
                  ? 'bg-primary-500 text-white shadow-lg shadow-primary-500/20'
                  : 'bg-dark-900 text-dark-300 hover:bg-dark-600 hover:text-dark-100 ring-1 ring-dark-600',
              )}
            >
              {chip.dot && <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', chip.dot)} />}
              {chip.label}
            </button>
          ))}
        </div>
      </div>

      {error && <ErrorState onRetry={() => refetch()} />}
      <ActionError message={actionError} onDismiss={() => setActionError(null)} />

      {/* ── Kanban View ─────────────────────────────────────────── */}
      {viewMode === 'kanban' && !isLoading && (
        <KanbanBoard<ReservationList>
          columns={(() => {
            const groups: Record<string, { label: string; color: string }> = {
              draft:     { label: 'Brouillon',  color: '#6b7280' },
              confirmed: { label: 'Confirmées', color: '#3b82f6' },
              pre_check: { label: 'Pré-check',  color: '#8b5cf6' },
              delivered: { label: 'En cours',   color: '#f59e0b' },
              returned:  { label: 'Retournées', color: '#22c55e' },
              completed: { label: 'Terminées',  color: '#10b981' },
            }
            return Object.entries(groups).map(([key, { label, color }]) => ({
              key, label, color,
              items: reservations.filter((r) => {
                if (key === 'confirmed') return r.status === 'confirmed' || r.status === 'confirmed_risk'
                if (key === 'delivered') return r.status === 'delivered' || r.status === 'extended'
                if (key === 'returned') return r.status === 'returned' || r.status === 'returned_dispute'
                return r.status === key
              }),
            })) as KanbanColumn<ReservationList>[]
          })()}
          renderCard={(r) => {
            const paymentColor =
              r.payment_status === 'paid' ? 'text-green-400 bg-green-500/10' :
              r.payment_status === 'partial' ? 'text-amber-400 bg-amber-500/10' :
              'text-dark-400 bg-dark-900'
            return (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-[11px] font-bold text-primary-400">{r.reference}</span>
                  <span className="text-sm font-bold text-dark-50 tabular-nums">{formatCents(r.total_amount_cents)}</span>
                </div>
                <p className="text-sm font-semibold text-dark-50 truncate">{r.customer_name || `Client #${r.customer_id}`}</p>
                <div className="flex items-center gap-2 text-[11px] text-dark-400">
                  <CalendarCheck className="w-3 h-3" />{formatDate(r.event_date)}
                  {r.event_location && <><MapPin className="w-3 h-3 ml-1" /><span className="truncate">{r.event_location}</span></>}
                </div>
                <div className="flex items-center gap-1.5 pt-1.5 border-t border-dark-600">
                  <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-semibold', paymentColor)}>
                    <CreditCard className="w-2.5 h-2.5 inline mr-0.5" />
                    {r.payment_status === 'paid' ? 'Payé' : r.payment_status === 'partial' ? 'Partiel' : 'Impayé'}
                  </span>
                  {r.deposit_paid && <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold text-green-400 bg-green-500/10">Caution ✓</span>}
                  {r.event_type && <span className="ml-auto text-[10px] text-primary-400/70">{EVENT_TYPE_LABELS[r.event_type] || r.event_type}</span>}
                </div>
              </div>
            )
          }}
          onCardClick={(r) => navigate({ to: '/reservations/$id', params: { id: String(r.id) } })}
        />
      )}

      {/* ── Card List View ──────────────────────────────────────── */}
      {viewMode === 'list' && (
        <div className="space-y-2">
          {isLoading ? (
            Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)
          ) : reservations.length === 0 ? (
            currentStatus
              ? <NoSearchResults onClear={() => setStatus('')} />
              : <NoData onAction={canWrite ? () => navigate({ to: '/devis/new' }) : undefined} actionLabel="Nouveau devis" />
          ) : (
            reservations.map((r) => (
              <SwipeActions
                key={r.id}
                leftActions={[
                  { icon: <CreditCard className="w-4 h-4" />, label: 'Paiement', color: 'bg-emerald-600', onClick: () => navigate({ to: '/reservations/$id', params: { id: String(r.id) } }) },
                ]}
                rightActions={[
                  ...(canWrite && r.status === 'draft' ? [
                    { icon: <Check className="w-4 h-4" />, label: 'Confirmer', color: 'bg-blue-600', onClick: () => confirmMutation.mutate(r.id, { onError: onErr }) },
                  ] : canWrite && (r.status === 'confirmed' || r.status === 'pre_check') ? [
                    { icon: <Truck className="w-4 h-4" />, label: 'Livrer', color: 'bg-amber-600', onClick: () => deliverMutation.mutate(r.id, { onError: onErr }) },
                  ] : r.status === 'returned' ? [
                    { icon: <PackageCheck className="w-4 h-4" />, label: 'Clôturer', color: 'bg-emerald-600', onClick: () => completeMutation.mutate(r.id, { onError: onErr }) },
                  ] : []),
                  ...(canWrite && (r.status === 'draft' || r.status === 'confirmed') ? [
                    { icon: <XCircle className="w-4 h-4" />, label: 'Annuler', color: 'bg-red-600', onClick: () => cancelMutation.mutate(r.id, { onError: onErr }) },
                  ] : []),
                ] as SwipeAction[]}
              >
                <ReservationCard
                  r={r}
                  onNavigate={() => navigate({ to: '/reservations/$id', params: { id: String(r.id) } })}
                  highlight={r.id === highlight}
                />
              </SwipeActions>
            ))
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <span className="text-sm text-dark-400">Page {page}/{totalPages}</span>
              <div className="flex gap-2">
                <button type="button" onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="btn-secondary disabled:opacity-30">
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button type="button" onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages} className="btn-secondary disabled:opacity-30">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Modals ──────────────────────────────────────────────── */}
      {(modal.isOpen('create') || modal.isOpen('edit')) && (
        <ReservationFormModal
          isOpen
          onClose={modal.close}
          reservation={modal.data}
          mode={modal.isOpen('edit') ? 'edit' : 'create'}
        />
      )}
    </div>
  )
}
