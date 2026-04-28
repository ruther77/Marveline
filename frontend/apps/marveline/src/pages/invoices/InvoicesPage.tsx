import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useNavigate, useSearch, Link } from '@tanstack/react-router'
import { useInvoicesList, useCancelInvoice, useInvoiceSequenceGaps } from '@/api/queries'
import { ErrorState, NoData, NoSearchResults } from '@shared/components/ui/EmptyState'
import { useMultiModal } from '@/hooks/useModal'
import { InvoiceDetailModal, InvoiceSendModal } from './components'
import type { InvoiceListItem, InvoiceStatus } from '@/types/invoice'
import { useInvoiceFilters } from '@/stores/filterStore'
import {
  FileText, Send, XCircle, ChevronLeft, ChevronRight, Plus,
  AlertTriangle, CreditCard, Clock, CheckCircle, Download, Bell,
} from 'lucide-react'
import { cn, formatDate, formatCents } from '@/lib/utils'
import { normalizeError } from '@shared/errors/normalizer'
import { PAGE_SIZE_DEFAULT } from '@/lib/constants'
import { DomainStatusBadge, ActionError, PaymentProgressBar, SwipeActions } from '@shared/components/ui'

// ── Status config ──────────────────────────────────────────────────────────
const STATUS_CFG: Record<string, { label: string; dot: string; border: string }> = {
  draft:     { label: 'Brouillon', dot: 'bg-dark-400',   border: 'border-l-dark-400' },
  sent:      { label: 'Envoyée',   dot: 'bg-blue-500',   border: 'border-l-blue-500' },
  paid:      { label: 'Payée',     dot: 'bg-green-500',  border: 'border-l-green-500' },
  overdue:   { label: 'En retard', dot: 'bg-red-500',    border: 'border-l-red-500' },
  cancelled: { label: 'Annulée',   dot: 'bg-dark-500',   border: 'border-l-dark-500' },
}

const STATUS_CHIPS: { value: InvoiceStatus | ''; label: string; dot?: string }[] = [
  { value: '', label: 'Toutes' },
  ...Object.entries(STATUS_CFG).map(([k, v]) => ({ value: k as InvoiceStatus, label: v.label, dot: v.dot })),
]

// ── Skeleton ───────────────────────────────────────────────────────────────
function InvoiceCardSkeleton() {
  return (
    <div className="rounded-xl border border-dark-600 border-l-4 border-l-dark-600 bg-dark-900 p-4 animate-pulse">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-3">
          <div className="flex items-center gap-3"><div className="h-4 bg-dark-900 rounded w-28" /><div className="h-5 bg-dark-900 rounded-full w-16" /></div>
          <div className="h-3 skel rounded w-36" />
          <div className="h-1.5 skel rounded w-40" />
        </div>
        <div className="h-5 skel rounded w-20" />
      </div>
    </div>
  )
}

// ── Invoice Card ───────────────────────────────────────────────────────────
function InvoiceCard({ inv, onView, onSend, onCancel, onPay, canCancel }: {
  inv: InvoiceListItem
  onView: () => void
  onSend: () => void
  onCancel: () => void
  onPay: () => void
  canCancel: boolean
}) {
  const cfg = STATUS_CFG[inv.status] ?? STATUS_CFG.draft

  return (
    <SwipeActions
      leftActions={[
        ...(canCancel ? [{ label: 'Annuler', icon: <XCircle className="w-4 h-4" />, color: 'bg-red-600', onClick: onCancel }] : []),
      ]}
      rightActions={[
        ...(inv.status === 'draft' ? [{ label: 'Envoyer', icon: <Send className="w-4 h-4" />, color: 'bg-blue-600', onClick: onSend }] : []),
        ...(inv.status === 'sent' || inv.status === 'overdue' ? [{ label: 'Relancer', icon: <Bell className="w-4 h-4" />, color: 'bg-amber-600', onClick: onSend }] : []),
        ...(!inv.is_paid && inv.status !== 'cancelled' ? [{ label: 'Payer', icon: <CreditCard className="w-4 h-4" />, color: 'bg-emerald-600', onClick: onPay }] : []),
      ]}
    >
      <button
        type="button"
        onClick={onView}
        className={cn(
          'w-full text-left rounded-xl border border-dark-600 border-l-4 bg-dark-900',
          'hover:bg-dark-600 hover:border-dark-600 transition-all',
          cfg.border,
        )}
      >
        <div className="p-4">
          {/* Row 1 : Numéro + Status + Amount */}
          <div className="flex items-center justify-between gap-3 mb-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="font-mono text-xs font-bold text-primary-400">{inv.invoice_number}</span>
              <DomainStatusBadge status={inv.status} size="sm" />
              {inv.is_overdue && (
                <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold text-red-400 bg-red-500/10">
                  <AlertTriangle className="w-3 h-3" /> Retard
                </span>
              )}
            </div>
            <span className="text-base font-bold text-dark-50 tabular-nums shrink-0">
              {formatCents(inv.total_amount_cents)}
            </span>
          </div>

          {/* Row 2 : Client */}
          <p className="text-sm font-semibold text-dark-100 truncate mb-1.5">
            {inv.customer_name || '—'}
          </p>

          {/* Row 3 : Dates */}
          <div className="flex items-center gap-3 text-xs text-dark-400 mb-3">
            <span className="flex items-center gap-1">
              <FileText className="w-3 h-3 text-dark-500" />
              {formatDate(inv.issue_date)}
            </span>
            <span className="text-dark-600">|</span>
            <span className={cn('flex items-center gap-1', inv.is_overdue && 'text-red-400')}>
              <Clock className="w-3 h-3" />
              Echéance {formatDate(inv.due_date)}
            </span>
          </div>

          {/* Row 4 : Payment bar */}
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <PaymentProgressBar paidCents={inv.paid_amount_cents} totalCents={inv.total_amount_cents} size="sm" />
            </div>
          </div>
        </div>
      </button>
    </SwipeActions>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────
type ModalType = 'details'

export default function InvoicesPage() {
  const navigate = useNavigate({ from: '/finance/invoices/' })
  const { page, reservation_id: reservationId } = useSearch({ strict: false }) as { page: number; reservation_id?: number }
  const setPage = (p: number) => navigate({ search: (prev) => ({ ...prev, page: p }) })
  const { filters: invFilters, set: setInvFilters, reset: resetInvFilters } = useInvoiceFilters()
  const statusFilter = (invFilters.status[0] as InvoiceStatus) || ''
  const modal = useMultiModal<InvoiceListItem>()
  const [actionError, setActionError] = useState<string | null>(null)
  const [sendTarget, setSendTarget] = useState<InvoiceListItem | null>(null)

  const { data, isLoading, error, refetch } = useInvoicesList({ skip: (page - 1) * PAGE_SIZE_DEFAULT, limit: PAGE_SIZE_DEFAULT, status: statusFilter || undefined, reservation_id: reservationId })
  const cancelMutation = useCancelInvoice()
  const currentYear = new Date().getFullYear()
  const { data: gapsData } = useInvoiceSequenceGaps(currentYear)

  const invoices = data?.items || []
  const totalPages = Math.ceil((data?.total ?? 0) / PAGE_SIZE_DEFAULT) || 1

  return (
    <div className="space-y-5">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Factures" subtitle={data?.total !== undefined ? `${data.total} facture${(data.total ?? 0) > 1 ? 's' : ''}` : 'Gérez vos factures clients'} />
        <Link to="/finance/invoices/new" className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /><span className="hidden sm:inline">Nouvelle facture</span>
        </Link>
      </div>

      {/* ── Sequence gaps alert ─────────────────────────────────── */}
      {gapsData && gapsData.count > 0 && (
        <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-400 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>
            Séquence {currentYear} — {gapsData.count} trou{gapsData.count > 1 ? 's' : ''} :{' '}
            <span className="font-mono">{gapsData.gaps.slice(0, 5).map((n: number) => `INV-${currentYear}-${String(n).padStart(4, '0')}`).join(', ')}{gapsData.gaps.length > 5 ? ` …` : ''}</span>
          </span>
        </div>
      )}

      {/* ── Status chips ────────────────────────────────────────── */}
      <div className="overflow-x-auto -mx-4 px-4">
        <div className="flex gap-1.5 pb-1 min-w-max">
          {STATUS_CHIPS.map((chip) => (
            <button
              key={chip.value}
              onClick={() => { setInvFilters({ status: chip.value ? [chip.value] : [] }); setPage(1) }}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all',
                statusFilter === chip.value
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

      {/* ── Cards ───────────────────────────────────────────────── */}
      <div className="space-y-2">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => <InvoiceCardSkeleton key={i} />)
        ) : invoices.length === 0 ? (
          statusFilter
            ? <NoSearchResults onClear={() => { resetInvFilters(); setPage(1) }} />
            : <NoData onAction={() => navigate({ to: '/finance/invoices/new' })} actionLabel="Nouvelle facture" />
        ) : (
          invoices.map((inv) => (
            <InvoiceCard
              key={inv.id}
              inv={inv}
              onView={() => modal.open('details', inv)}
              onSend={() => setSendTarget(inv)}
              onPay={() => navigate({ to: '/finance/invoices/$id', params: { id: String(inv.id) }, search: { tab: 'paiement' } })}
              onCancel={() => cancelMutation.mutate(inv.id, { onError: (err) => setActionError(normalizeError(err).message || "Erreur") })}
              canCancel={inv.status !== 'paid' && inv.status !== 'cancelled'}
            />
          ))
        )}
      </div>

      {/* ── Pagination ──────────────────────────────────────────── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-sm text-dark-400">Page {page}/{totalPages} ({data?.total ?? 0})</span>
          <div className="flex gap-2">
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="btn-secondary disabled:opacity-30"><ChevronLeft className="w-4 h-4" /></button>
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages} className="btn-secondary disabled:opacity-30"><ChevronRight className="w-4 h-4" /></button>
          </div>
        </div>
      )}

      {/* ── Modals ──────────────────────────────────────────────── */}
      <InvoiceDetailModal isOpen={modal.isOpen('details')} onClose={modal.close} invoiceId={modal.data?.id} />
      <InvoiceSendModal isOpen={sendTarget !== null} onClose={() => setSendTarget(null)} invoice={sendTarget} />
    </div>
  )
}
