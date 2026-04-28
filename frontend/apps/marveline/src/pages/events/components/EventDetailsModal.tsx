import { useEffect, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { normalizeError } from '@shared/errors/normalizer'
import {
  useReservationDetail, useReservationFull, useReservationDeposits,
  useConfirmReservation, useCancelReservation, useDeliverReservation,
  useCompleteReservation, useAssignReservationUser, useCloseReservationDispute,
  useMovementsList, useInvoicesList, useCreateInvoice,
  useEntityAuditLogs, useUsers,
} from '@/api/queries'
import { useRemindReservationDeposit } from '@/api/queries/useReservations'
import { Modal } from '@shared/components/ui/Modal'
import { ActionError } from '@shared/components/ui/ActionError'
import { TimelineAudit } from '@shared/components/ui/TimelineAudit'
import type { TimelineEntry } from '@shared/components/ui/TimelineAudit'
import { formatDate, formatCents, cn } from '@/lib/utils'
import {
  RESERVATION_STATUS_LABELS as STATUS_LABELS,
  RESERVATION_STATUS_COLORS as STATUS_COLORS,
  EVENT_TYPE_LABELS,
  EVENT_TYPE_COLORS,
  MOVEMENT_STATUS_LABELS,
  MOVEMENT_STATUS_COLORS,
} from '@/lib/constants'
import {
  Calendar, MapPin, Package, Check, XCircle, CheckCircle,
  Truck, RotateCcw, FileText, ArrowUpFromLine, ArrowDownToLine, PackageCheck, Users, Pen,
  Clock, Info, CreditCard, ExternalLink,
} from 'lucide-react'
import type { Deposit } from '@/types/deposit'
import type { ReservationDetail, ReservationStatus } from '@/types/reservation'
import { DepositSection } from './DepositSection'
import { PreCheckSection } from './PreCheckSection'
import { ExtendSection } from './ExtendSection'
import { RisksSection } from './RisksSection'
import { CancelReservationModal } from './CancelReservationModal'
import { CloseDisputeModal } from './CloseDisputeModal'
import { useAuthStore } from '@/stores/authStore'

// ── Hero couleur selon statut ─────────────────────────────────────────────────
const HERO_BG: Record<string, string> = {
  draft:                    'bg-dark-900 border-dark-600',
  confirmed:                'bg-amber-950/40 border-amber-700/40',
  confirmed_risk:           'bg-red-950/40 border-red-700/40',
  pre_check:                'bg-green-950/40 border-green-700/40',
  delivered:                'bg-blue-950/40 border-blue-700/40',
  extended:                 'bg-blue-950/40 border-blue-700/40',
  returned:                 'bg-orange-950/40 border-orange-700/40',
  returned_dispute:         'bg-orange-950/40 border-orange-700/40',
  completed:                'bg-purple-950/40 border-purple-700/40',
  cancelled:                'bg-dark-900 border-dark-600',
}
const PROGRESS_COLOR: Record<string, string> = {
  confirmed:     'bg-amber-500',
  pre_check:     'bg-green-500',
  delivered:     'bg-blue-500',
  extended:      'bg-blue-500',
  returned:      'bg-orange-500',
  completed:     'bg-purple-500',
}

// ── Alert contextuelle selon statut ──────────────────────────────────────────
function StatusAlert({ reservation }: { reservation: ReservationDetail }) {
  const { status } = reservation
  if (status === 'draft') return (
    <div className="flex gap-2 p-4 rounded-lg bg-dark-900/60 border border-dark-600 text-sm text-dark-300">
      <Info className="w-4 h-4 text-dark-400 shrink-0 mt-0.5" />
      Complète les produits manquants puis confirme pour réserver le stock.
    </div>
  )
  if (status === 'confirmed_risk') return (
    <div className="flex gap-2 p-4 rounded-lg bg-red-900/20 border border-red-700/30 text-sm text-red-300">
      Caution + acompte en retard. Sans règlement, la sortie matériel doit être suspendue.
    </div>
  )
  if (status === 'confirmed') return (
    <div className="flex gap-2 p-4 rounded-lg bg-amber-900/20 border border-amber-700/30 text-sm text-amber-300">
      Le départ matériel reste bloqué tant que caution et acompte ne sont pas validés.
    </div>
  )
  if (status === 'pre_check') return (
    <div className="flex gap-2 p-4 rounded-lg bg-green-900/20 border border-green-700/30 text-sm text-green-300">
      <Check className="w-4 h-4 text-green-400 shrink-0 mt-0.5" />
      Caution et acompte valides. Le départ peut être lancé.
    </div>
  )
  if (status === 'delivered' || status === 'extended') return (
    <div className="flex gap-2 p-4 rounded-lg bg-blue-900/20 border border-blue-700/30 text-sm text-blue-300">
      <Truck className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
      Matériel sorti. Retour prévu le {formatDate(reservation.return_date)}.
    </div>
  )
  if (status === 'returned' || status === 'returned_dispute') return (
    <div className="flex gap-2 p-4 rounded-lg bg-orange-900/20 border border-orange-700/30 text-sm text-orange-300">
      {status === 'returned_dispute' ? 'Litige en cours — arbitrage en attente.' : 'Contrôle retour en cours.'}
    </div>
  )
  if (status === 'completed') return (
    <div className="flex gap-2 p-4 rounded-lg bg-purple-900/20 border border-purple-700/30 text-sm text-purple-300">
      <Check className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
      Réservation clôturée. Caution restituée.
    </div>
  )
  return null
}

// ── Focus pills contextuelles ─────────────────────────────────────────────────
function FocusPills({ reservation, deposit }: { reservation: ReservationDetail; deposit?: Deposit }) {
  const { status } = reservation
  const depositHeld = deposit?.status === 'held'
  const pills: { label: string; value: string; color?: string }[] = []

  if (status === 'draft') {
    pills.push({ label: 'Statut', value: 'Brouillon ouvert' })
    pills.push({ label: 'Articles', value: `${reservation.lines?.length ?? 0} ligne${(reservation.lines?.length ?? 0) !== 1 ? 's' : ''}` })
    pills.push({ label: 'Prochaine étape', value: 'Confirmer la réservation' })
  } else if (['confirmed', 'confirmed_risk', 'pre_check'].includes(status)) {
    pills.push({ label: 'Date événement', value: formatDate(reservation.event_date) })
    pills.push({ label: 'Stock', value: 'Réservé', color: 'text-green-400' })
    const cautionAmt = reservation.deposit_amount_cents
    if (cautionAmt > 0) {
      pills.push({ label: 'Caution', value: depositHeld ? `${formatCents(cautionAmt)} encaissée` : `${formatCents(cautionAmt)} en attente`, color: depositHeld ? 'text-green-400' : 'text-amber-400' })
    }
    pills.push({ label: 'Solde', value: `${formatCents(reservation.total_amount_cents)} à venir`, color: 'text-amber-400' })
  } else if (status === 'delivered' || status === 'extended') {
    pills.push({ label: 'Sorti le', value: formatDate(reservation.delivery_date) })
    pills.push({ label: 'Retour prévu', value: formatDate(reservation.return_date), color: 'text-amber-400' })
    pills.push({ label: 'Caution', value: depositHeld ? 'Encaissée' : 'En attente', color: depositHeld ? 'text-green-400' : 'text-red-400' })
    pills.push({ label: 'Solde restant', value: formatCents(reservation.total_amount_cents), color: 'text-red-400' })
  } else if (status === 'completed') {
    pills.push({ label: 'Total encaissé', value: formatCents(reservation.total_amount_cents), color: 'text-green-400' })
    pills.push({ label: 'Caution', value: 'Restituée', color: 'text-green-400' })
    pills.push({ label: 'Dommages', value: 'Aucun' })
  }

  if (pills.length === 0) return null
  return (
    <div className="flex gap-2 flex-wrap pb-1 lg:flex-nowrap lg:overflow-x-auto">
      {pills.map((p, i) => (
        <div key={i} className="shrink-0 card px-4 py-2 min-w-[100px]">
          <div className="text-xs text-dark-500">{p.label}</div>
          <div className={cn('text-xs font-semibold mt-0.5', p.color || 'text-dark-200')}>{p.value}</div>
        </div>
      ))}
    </div>
  )
}

// ── Composant principal ───────────────────────────────────────────────────────

interface ReservationDetailsModalProps {
  isOpen: boolean
  onClose: () => void
  reservationId?: number
}

export function ReservationDetailsModal({ isOpen, onClose, reservationId }: ReservationDetailsModalProps) {
  const navigate = useNavigate()
  const { user: currentUser } = useAuthStore()
  const [showCancelModal, setShowCancelModal] = useState(false)
  const [showCloseDisputeModal, setShowCloseDisputeModal] = useState(false)
  const [selectedAssignee, setSelectedAssignee] = useState('')
  const activeId = isOpen && reservationId ? reservationId : null

  const { data: reservationDetail } = useReservationDetail(activeId)
  const { data: reservation, isLoading } = useReservationFull(activeId)
  const { data: movementsData } = useMovementsList({ reservation_id: activeId ?? undefined, limit: 10 }, !!activeId)
  const { data: invoicesData } = useInvoicesList({ reservation_id: activeId ?? undefined }, !!activeId)
  const { data: deposits = [] } = useReservationDeposits(activeId)
  const { data: usersData, error: usersError } = useUsers({ skip: 0, limit: 200 }, !!activeId)
  const currentDeposit: Deposit | undefined = deposits[0]

  const confirmMutation = useConfirmReservation()
  const cancelMutation = useCancelReservation()
  const deliverMutation = useDeliverReservation()
  const completeMutation = useCompleteReservation()
  const closeDisputeMutation = useCloseReservationDispute()
  const remindDepositMutation = useRemindReservationDeposit()
  const assignMutation = useAssignReservationUser()
  const createInvoiceMutation = useCreateInvoice()

  const users = usersData?.items ?? []
  const assignedUserId =
    reservationDetail?.assigned_user_id ??
    (reservation as { assigned_user_id?: number | null } | undefined)?.assigned_user_id ??
    null
  const assigneeName = assignedUserId
    ? (users.find((u) => u.id === assignedUserId)?.full_name ?? `#${assignedUserId}`)
    : 'Non affectée'

  useEffect(() => {
    if (!isOpen) {
      setSelectedAssignee('')
      return
    }
    setSelectedAssignee(assignedUserId ? String(assignedUserId) : '')
  }, [isOpen, assignedUserId])

  const { data: auditLogsData } = useEntityAuditLogs('Reservation', activeId)
  const auditEntries: TimelineEntry[] = (auditLogsData?.items ?? []).map((log) => ({
    date: log.created_at,
    user: log.user_id ? `#${log.user_id}` : 'Système',
    action: log.action,
    detail: log.description ?? undefined,
    type: log.action.startsWith('reservation.status') ? 'state' : 'action',
  }))

  const linkedMovements = movementsData?.items || []
  const hasInvoice = (invoicesData?.total ?? 0) > 0

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Details de la reservation" size="full">
      {isLoading ? (
        <div className="space-y-4 animate-pulse">
          <div className="flex items-center justify-between gap-3">
            <div className="h-5 skel rounded w-32" />
            <div className="h-6 skel rounded w-20" />
          </div>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex justify-between py-2 border-b border-dark-600">
              <div className="h-3 skel rounded w-24" />
              <div className="h-3 skel rounded w-36" />
            </div>
          ))}
        </div>
      ) : reservation ? (
        <div className="space-y-4">

          {/* Hero */}
          <div className={cn('rounded-xl border p-4 space-y-4', HERO_BG[reservation.status] || 'bg-dark-900 border-dark-600')}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-base font-semibold text-primary-400">{reservation.reference}</span>
                  <span className={cn('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', STATUS_COLORS[reservation.status])}>
                    {STATUS_LABELS[reservation.status]}
                  </span>
                  {reservation.signature_url && (
                    <span className="text-xs text-green-400 flex items-center gap-1 px-2 py-0.5 bg-green-900/20 rounded border border-green-700/30">
                      <Check className="w-3 h-3" />Signé
                    </span>
                  )}
                </div>
                <p className="text-sm font-medium text-dark-100 mt-1">
                  {reservation.customer?.display_name || `Client #${reservation.customer_id}`}
                </p>
                <div className="flex items-center gap-4 mt-1 text-xs text-dark-400 flex-wrap">
                  <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{formatDate(reservation.event_date)}</span>
                  {reservation.event_location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{reservation.event_location}</span>}
                  {reservation.rental_days > 0 && <span>{reservation.rental_days}j de location</span>}
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-lg font-bold text-white">{formatCents(reservation.total_amount_cents)}</div>
                {reservation.deposit_amount_cents > 0 && (
                  <div className="text-xs text-dark-400">caution {formatCents(reservation.deposit_amount_cents)}</div>
                )}
              </div>
            </div>
            {PROGRESS_COLOR[reservation.status] && (() => {
              const ORDER: ReservationStatus[] = ['draft', 'confirmed', 'pre_check', 'delivered', 'returned', 'completed']
              const STAGE_STATUS: Record<string, ReservationStatus> = {
                confirmed_risk: 'confirmed',
                extended: 'delivered',
                returned_dispute: 'returned',
              }
              const stage = STAGE_STATUS[reservation.status] ?? (reservation.status as ReservationStatus)
              const idx = ORDER.indexOf(stage)
              const pct = idx < 0 ? 0 : Math.round(((idx + 1) / ORDER.length) * 100)
              return (
                <div className="h-1 bg-dark-900 rounded-full overflow-hidden">
                  <div className={cn('h-full rounded-full transition-all', PROGRESS_COLOR[reservation.status])} style={{ width: `${pct}%` }} />
                </div>
              )
            })()}
            <FocusPills reservation={reservation} deposit={currentDeposit} />
          </div>

          {/* Alert + erreurs */}
          <StatusAlert reservation={reservation} />
          <ActionError
            message={(confirmMutation.error || cancelMutation.error) ? normalizeError(confirmMutation.error || cancelMutation.error).message || 'Une erreur est survenue' : null}
            onDismiss={() => { confirmMutation.reset(); cancelMutation.reset() }}
          />
          <ActionError
            message={deliverMutation.error ? normalizeError(deliverMutation.error).message || 'Erreur lors de la livraison' : null}
            onDismiss={() => deliverMutation.reset()}
          />
          <ActionError
            message={completeMutation.error ? normalizeError(completeMutation.error).message || 'Erreur lors de la clôture' : null}
            onDismiss={() => completeMutation.reset()}
          />
          <ActionError
            message={closeDisputeMutation.error ? normalizeError(closeDisputeMutation.error).message || 'Erreur lors de la clôture du litige' : null}
            onDismiss={() => closeDisputeMutation.reset()}
          />
          <ActionError
            message={remindDepositMutation.error ? normalizeError(remindDepositMutation.error).message || 'Erreur lors de la relance caution' : null}
            onDismiss={() => remindDepositMutation.reset()}
          />
          <ActionError
            message={assignMutation.error ? normalizeError(assignMutation.error).message || "Erreur lors de l'affectation" : null}
            onDismiss={() => assignMutation.reset()}
          />
          <ActionError
            message={createInvoiceMutation.error ? normalizeError(createInvoiceMutation.error).message || 'Erreur lors de la création de la facture' : null}
            onDismiss={() => createInvoiceMutation.reset()}
          />
          {createInvoiceMutation.isSuccess && (
            <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
              Facture générée avec succès.{' '}
              <Link to="/finance/invoices" className="underline">Voir les factures</Link>
            </div>
          )}

          {/* Affectation */}
          {reservation.status !== 'cancelled' && reservation.status !== 'completed' && (
            <div className="p-4 border border-dark-600 rounded-lg bg-dark-900/40 space-y-2">
              <div className="flex items-center justify-between gap-4">
                <span className="text-sm text-dark-400">Responsable</span>
                <span className="text-sm font-medium">{assigneeName}</span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <select
                  value={selectedAssignee}
                  onChange={(e) => setSelectedAssignee(e.target.value)}
                  className="input text-sm min-w-[180px]"
                >
                  <option value="">Non affectée</option>
                  {users.map((u) => (
                    <option key={u.id} value={String(u.id)}>
                      {u.full_name || u.email}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => assignMutation.mutate({ reservationId: reservation.id, userId: selectedAssignee ? Number(selectedAssignee) : null })}
                  disabled={assignMutation.isPending}
                  className="btn-secondary btn-sm"
                >
                  {assignMutation.isPending ? 'Affectation…' : 'Affecter'}
                </button>
                {currentUser?.id && (
                  <button
                    type="button"
                    onClick={() => assignMutation.mutate({ reservationId: reservation.id, userId: currentUser.id })}
                    disabled={assignMutation.isPending}
                    className="btn-secondary btn-sm"
                  >
                    M&apos;affecter
                  </button>
                )}
              </div>
              {usersError && (
                <p className="text-xs text-amber-400">
                  Liste utilisateurs indisponible (scope `users:read` requis).
                </p>
              )}
            </div>
          )}

          {/* Actions CTA */}
          <div className="flex gap-2 flex-wrap">
            {reservation.status === 'draft' && (
              <button onClick={() => confirmMutation.mutate(reservation.id)} disabled={confirmMutation.isPending} className="btn-primary btn-sm flex items-center gap-1">
                <Check className="w-3 h-3" />{confirmMutation.isPending ? 'Confirmation…' : 'Confirmer'}
              </button>
            )}
            {['confirmed', 'pre_check'].includes(reservation.status) && (
              <button onClick={() => deliverMutation.mutate(reservation.id)} disabled={deliverMutation.isPending} className="btn-primary btn-sm flex items-center gap-1">
                <PackageCheck className="w-3 h-3" />{deliverMutation.isPending ? 'Enregistrement…' : 'Marquer livrée'}
              </button>
            )}
            {(reservation.status === 'delivered' || reservation.status === 'extended') && (
              <button onClick={() => { onClose(); navigate({ to: '/operations/return/$reservationId', params: { reservationId: String(reservation.id) } }) }} className="btn-primary btn-sm flex items-center gap-1">
                <RotateCcw className="w-3 h-3" />Créer retour
              </button>
            )}
            {reservation.status === 'returned' && (
              <button onClick={() => completeMutation.mutate(reservation.id)} disabled={completeMutation.isPending} className="btn-primary btn-sm flex items-center gap-1">
                <CheckCircle className="w-3 h-3" />{completeMutation.isPending ? 'Clôture…' : 'Clôturer'}
              </button>
            )}
            {['confirmed', 'confirmed_risk', 'pre_check'].includes(reservation.status) && reservation.deposit_amount_cents > 0 && currentDeposit?.status !== 'held' && (
              <button onClick={() => remindDepositMutation.mutate(reservation.id)} disabled={remindDepositMutation.isPending} className="btn-secondary btn-sm flex items-center gap-1">
                <CreditCard className="w-3 h-3" />{remindDepositMutation.isPending ? 'Relance…' : 'Relancer caution'}
              </button>
            )}
            {!hasInvoice && reservation.status !== 'cancelled' && reservation.status !== 'draft' && (
              <button
                onClick={() => {
                  const today = new Date().toISOString().split('T')[0]
                  const computed = new Date(new Date(reservation.event_date).getTime() - 7 * 86400000).toISOString().split('T')[0]
                  const dueDate = computed > today ? computed : new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0]
                  createInvoiceMutation.mutate({ reservation_id: reservation.id, issue_date: today, due_date: dueDate })
                }}
                disabled={createInvoiceMutation.isPending}
                className="btn-secondary btn-sm flex items-center gap-1"
              >
                <FileText className="w-3 h-3" />{createInvoiceMutation.isPending ? 'Création…' : 'Générer facture'}
              </button>
            )}
            {!reservation.signature_url && reservation.status !== 'cancelled' && (
              <button onClick={() => { onClose(); navigate({ to: '/reservations/$id/signature', params: { id: String(reservation.id) } }) }} className="btn-secondary btn-sm flex items-center gap-1">
                <Pen className="w-3 h-3" />Signer
              </button>
            )}
            {(reservation.status === 'draft' || reservation.status === 'confirmed') && (
              <button
                onClick={() => setShowCancelModal(true)}
                className="btn-secondary btn-sm flex items-center gap-1 text-red-400 hover:text-red-300"
              >
                <XCircle className="w-3 h-3" />Annuler
              </button>
            )}
            {reservation.status === 'returned_dispute' && (
              <button
                onClick={() => setShowCloseDisputeModal(true)}
                className="btn-secondary btn-sm flex items-center gap-1 text-green-400 hover:text-green-300"
              >
                <CheckCircle className="w-3 h-3" />Clore le litige
              </button>
            )}
          </div>

          {/* Info-grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-dark-900/60 rounded-lg p-4">
              <div className="text-xs text-dark-500 mb-1 flex items-center gap-1"><ArrowUpFromLine className="w-3 h-3" />Livraison</div>
              <div className="text-sm font-medium">{formatDate(reservation.delivery_date)}</div>
            </div>
            <div className="bg-dark-900/60 rounded-lg p-4">
              <div className="text-xs text-dark-500 mb-1 flex items-center gap-1"><Calendar className="w-3 h-3" />Événement</div>
              <div className="text-sm font-medium">{formatDate(reservation.event_date)}</div>
            </div>
            <div className="bg-dark-900/60 rounded-lg p-4">
              <div className="text-xs text-dark-500 mb-1 flex items-center gap-1"><ArrowDownToLine className="w-3 h-3" />Retour</div>
              <div className="text-sm font-medium">{formatDate(reservation.return_date)}</div>
            </div>
            <div className="bg-dark-900/60 rounded-lg p-4">
              <div className="text-xs text-dark-500 mb-1 flex items-center gap-1"><Package className="w-3 h-3" />Articles</div>
              <div className="text-sm font-medium">{reservation.lines?.length ?? 0} ligne{(reservation.lines?.length ?? 0) !== 1 ? 's' : ''}</div>
            </div>
          </div>

          {/* Détails événement */}
          {(reservation.event_type || reservation.event_name || reservation.guest_count) && (
            <div className="flex flex-wrap gap-4 text-sm">
              {reservation.event_type && (
                <span className={cn('inline-flex items-center px-2 py-1 rounded text-xs', EVENT_TYPE_COLORS[reservation.event_type] || 'bg-dark-900 text-dark-400')}>
                  {EVENT_TYPE_LABELS[reservation.event_type] || reservation.event_type}
                </span>
              )}
              {reservation.event_name && <span className="text-dark-300">{reservation.event_name}</span>}
              {reservation.guest_count && (
                <span className="flex items-center gap-1 text-dark-400"><Users className="w-3 h-3" />{reservation.guest_count} invités</span>
              )}
            </div>
          )}

          {/* Produits */}
          <div className="border-t border-dark-600 pt-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium flex items-center gap-2">
                <Package className="w-4 h-4" />
                Produits ({reservation.lines?.length || 0})
              </h3>
              {reservation.status === 'draft' && (
                <button onClick={() => { onClose(); navigate({ to: `/reservations/$id/lines`, params: { id: String(reservation.id) } }) }} className="text-sm text-primary-400 hover:text-primary-300">
                  Gérer les lignes →
                </button>
              )}
            </div>
            {reservation.lines && reservation.lines.length > 0 ? (
              <div className="space-y-2">
                {reservation.lines.map((line) => {
                  const imageUrl = line.product?.image_url
                  const name = line.variant?.label || line.bundle?.name || line.product?.name || `Article #${line.id}`
                  const subName = line.variant && line.product ? line.product.name : undefined
                  const sku = line.product?.sku || line.variant?.sku
                  return (
                    <div key={line.id} className="p-3 card flex gap-3 items-center">
                      <div className="w-12 h-12 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
                        {imageUrl ? (
                          <img src={imageUrl} alt={name} className="w-full h-full object-cover" loading="lazy" />
                        ) : (
                          <Package className="w-5 h-5 text-dark-600" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm truncate">{name}</div>
                        {subName && <div className="text-xs text-dark-400 truncate">{subName}</div>}
                        {sku && <div className="text-xs text-dark-500 font-mono mt-0.5">{sku}</div>}
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-xs text-dark-400">
                          {line.quantity} × {formatCents(line.unit_price_cents)}/j
                          {reservation.rental_days > 1 && <span> × {reservation.rental_days}j</span>}
                        </div>
                        <div className="font-semibold text-sm text-green-400">{formatCents(line.subtotal_cents)}</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-center py-6 border border-dashed border-dark-600 rounded-lg">
                <Package className="w-10 h-10 text-dark-600 mx-auto mb-2" />
                <p className="text-sm text-dark-400">Aucun produit</p>
              </div>
            )}
          </div>

          {/* Section Mouvements supprimée — info dans timeline terrain ci-dessous */}

          {/* Timeline terrain */}
          <div className="border-t border-dark-600 pt-4">
            <h3 className="font-medium flex items-center gap-2 mb-4"><Clock className="w-4 h-4" />Étapes terrain</h3>
            {(() => {
              const depMv = linkedMovements.find((m) => m.movement_type === 'departure')
              const retMv = linkedMovements.find((m) => m.movement_type === 'return')
              const DONE_STATUSES: ReservationStatus[] = ['delivered', 'extended', 'returned', 'returned_dispute', 'completed']
              const isDelivered = DONE_STATUSES.includes(reservation.status)
              const isReturned = ['returned', 'returned_dispute', 'completed'].includes(reservation.status)
              const steps = [
                { label: 'Réservation créée', date: reservation.created_at, done: true, color: 'bg-green-500' },
                { label: 'Livraison / Départ matériel', date: depMv?.scheduled_date || reservation.delivery_date, done: isDelivered, color: isDelivered ? 'bg-green-500' : 'bg-dark-600', note: depMv ? `Mvt #${depMv.id} — ${depMv.status}` : undefined },
                { label: 'Événement', date: reservation.event_date, done: isDelivered, color: isDelivered ? 'bg-green-500' : 'bg-dark-600' },
                { label: 'Retour prévu', date: retMv?.scheduled_date || reservation.return_date, done: isReturned, color: isReturned ? 'bg-green-500' : retMv ? 'bg-amber-500' : 'bg-dark-600', note: retMv ? `Mvt #${retMv.id} — ${retMv.status}` : undefined },
                { label: 'Clôture', date: undefined, done: reservation.status === 'completed', color: reservation.status === 'completed' ? 'bg-green-500' : 'bg-dark-600' },
              ]
              return (
                <ol className="relative ml-2 border-l border-dark-600 space-y-4">
                  {steps.map((s, i) => (
                    <li key={i} className="ml-6">
                      <span className={`absolute -left-[9px] w-4 h-4 rounded-full border-2 border-dark-900 ${s.color}`} />
                      <p className={`text-sm font-medium ${s.done ? 'text-white' : 'text-dark-500'}`}>{s.label}</p>
                      {s.date && <p className="text-xs text-dark-400">{formatDate(s.date)}</p>}
                      {s.note && <p className="text-xs text-dark-500">{s.note}</p>}
                    </li>
                  ))}
                </ol>
              )
            })()}
          </div>

          {/* Total */}
          <div className="border-t border-dark-600 pt-4">
            <div className="flex justify-between items-center text-lg font-bold">
              <span>Total</span>
              <span className="text-green-500">{formatCents(reservation.total_amount_cents)}</span>
            </div>
          </div>

          {/* Sections extraites */}
          <DepositSection reservation={reservation} reservationId={reservation.id} currentDeposit={currentDeposit} />

          {/* Facturation & Acompte */}
          {hasInvoice && invoicesData?.items && invoicesData.items.length > 0 && (
            <div className="border-t border-dark-600 pt-4">
              <h3 className="font-medium flex items-center gap-2 mb-4">
                <CreditCard className="w-4 h-4" /> Facturation
              </h3>
              <div className="space-y-2">
                {invoicesData.items.map((inv) => {
                  const remaining = inv.total_amount_cents - (inv.paid_amount_cents ?? 0)
                  const paidPct = inv.total_amount_cents > 0 ? Math.round(((inv.paid_amount_cents ?? 0) / inv.total_amount_cents) * 100) : 0
                  return (
                    <div key={inv.id} className="p-4 card space-y-2">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm">{inv.invoice_number}</span>
                          <span className={cn(
                            'text-xs px-2 py-0.5 rounded',
                            inv.status === 'paid' ? 'bg-green-500/20 text-green-400' :
                            inv.status === 'cancelled' ? 'bg-red-500/20 text-red-400' :
                            'bg-amber-500/20 text-amber-400'
                          )}>
                            {inv.status === 'paid' ? 'Payée' : inv.status === 'cancelled' ? 'Annulée' : inv.status === 'sent' ? 'Envoyée' : 'Brouillon'}
                          </span>
                        </div>
                        <span className="text-sm font-medium">{formatCents(inv.total_amount_cents)}</span>
                      </div>
                      {inv.status !== 'paid' && inv.status !== 'cancelled' && (
                        <div className="space-y-1">
                          <div className="flex justify-between text-xs text-dark-400">
                            <span>Payé : {formatCents(inv.paid_amount_cents ?? 0)} / {formatCents(inv.total_amount_cents)}</span>
                            <span>Reste : {formatCents(remaining)}</span>
                          </div>
                          <div className="h-1.5 bg-dark-900 rounded-full overflow-hidden">
                            <div className="h-full bg-green-500 rounded-full transition-all" style={{ width: `${paidPct}%` }} />
                          </div>
                        </div>
                      )}
                      <Link
                        to="/finance/invoices"
                        search={{ reservation_id: reservation.id, page: 1 }}
                        className="inline-flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300"
                      >
                        <ExternalLink className="w-3 h-3" />
                        {inv.status !== 'paid' && inv.status !== 'cancelled' ? 'Enregistrer un paiement' : 'Voir la facture'}
                      </Link>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          <PreCheckSection reservation={reservation} />
          <ExtendSection reservation={reservation} />
          <RisksSection reservation={reservation} />

          {/* Historique */}
          {auditEntries.length > 0 && (
            <div className="border-t border-dark-600 pt-4">
              <label className="text-sm text-dark-400 mb-4 block">Historique</label>
              <TimelineAudit entries={auditEntries} />
            </div>
          )}

          {/* Notes */}
          {reservation.notes && (
            <div className="border-t border-dark-600 pt-4">
              <label className="text-sm text-dark-400">Notes</label>
              <p className="text-sm mt-1">{reservation.notes}</p>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-8 text-dark-400">Reservation introuvable</div>
      )}
      {reservation && (
        <>
          <CancelReservationModal
            isOpen={showCancelModal}
            onClose={() => setShowCancelModal(false)}
            onConfirm={() => {
              cancelMutation.mutate(reservation.id, {
                onSuccess: () => setShowCancelModal(false),
              })
            }}
            loading={cancelMutation.isPending}
            reference={reservation.reference}
          />
          <CloseDisputeModal
            isOpen={showCloseDisputeModal}
            onClose={() => setShowCloseDisputeModal(false)}
            onConfirm={(resolutionNotes) => {
              closeDisputeMutation.mutate(
                { reservationId: reservation.id, resolutionNotes },
                { onSuccess: () => setShowCloseDisputeModal(false) },
              )
            }}
            loading={closeDisputeMutation.isPending}
            error={
              closeDisputeMutation.error
                ? normalizeError(closeDisputeMutation.error).message || 'Erreur lors de la clôture du litige'
                : null
            }
          />
        </>
      )}
    </Modal>
  )
}
