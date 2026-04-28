import { PageHeader } from '@/components/PageHeader'
import { useState, type ReactNode } from 'react'
import { useNavigate, useSearch } from '@tanstack/react-router'
import {
  FileText, Plus, Search, Copy, X, CheckCircle, Clock, AlertCircle,
  ChevronLeft, ChevronRight, CalendarCheck, MapPin, CreditCard, Send,
  ArrowRightCircle,
} from 'lucide-react'
import { useDevisList, useDevisStats, useDevisMutations } from '@/api/queries/useDevis'
import { useDebounce } from '@/hooks/useDebounce'
import { useHasScope } from '@/hooks/useHasScope'
import { cn, formatDate, formatCents } from '@/lib/utils'
import { DomainStatusBadge } from '@shared/components/ui'
import { SwipeActions } from '@shared/components/ui/SwipeActions'
import type { DevisStatus, DevisListItem } from '@/types/devis'

const CANCELLABLE_STATUSES: DevisStatus[] = ['draft', 'version_pending', 'accepted']

// ── Status config ──────────────────────────────────────────────────────────
const STATUS_CFG: Record<string, { label: string; dot: string; border: string }> = {
  draft:           { label: 'Brouillon',    dot: 'bg-dark-400',   border: 'border-l-dark-400' },
  sent:            { label: 'Envoyé',       dot: 'bg-blue-500',   border: 'border-l-blue-500' },
  negotiation:     { label: 'Négociation',  dot: 'bg-amber-500',  border: 'border-l-amber-500' },
  version_pending: { label: 'En révision',  dot: 'bg-amber-400',  border: 'border-l-amber-400' },
  accepted:        { label: 'Accepté',      dot: 'bg-green-500',  border: 'border-l-green-500' },
  converted:       { label: 'Converti',     dot: 'bg-emerald-500', border: 'border-l-emerald-500' },
  expired:         { label: 'Expiré',       dot: 'bg-red-400',    border: 'border-l-red-400' },
  refused:         { label: 'Refusé',       dot: 'bg-red-500',    border: 'border-l-red-500' },
  cancelled:       { label: 'Annulé',       dot: 'bg-dark-500',   border: 'border-l-dark-500' },
}

const STATUS_CHIPS: { value: DevisStatus | ''; label: string; dot?: string }[] = [
  { value: '', label: 'Tous' },
  ...Object.entries(STATUS_CFG).map(([k, v]) => ({ value: k as DevisStatus, label: v.label, dot: v.dot })),
]

const PAGE_SIZE = 20

// ── Skeleton ───────────────────────────────────────────────────────────────
function DevisCardSkeleton() {
  return (
    <div className="card rounded-xl border-l-4 border-l-dark-600 p-4 animate-pulse">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-3">
          <div className="flex items-center gap-3">
            <div className="h-4 skel rounded w-20" />
            <div className="h-5 skel rounded-full w-16" />
          </div>
          <div className="h-3 skel rounded w-36" />
          <div className="h-2 skel rounded w-48" />
        </div>
        <div className="h-5 skel rounded w-20" />
      </div>
    </div>
  )
}

// ── Devis Card ─────────────────────────────────────────────────────────────
function DevisCard({ d, onNavigate, canWrite, onDuplicate, onCancel, onSend, onConvert }: {
  d: DevisListItem
  onNavigate: () => void
  canWrite: boolean
  onDuplicate: () => void
  onCancel: () => void
  onSend: () => void
  onConvert: () => void
}) {
  const cfg = STATUS_CFG[d.status] ?? STATUS_CFG.draft

  return (
    <SwipeActions
      leftActions={canWrite ? [
        { label: 'Dupliquer', icon: <Copy className="w-4 h-4" />, color: 'bg-primary-600', onClick: onDuplicate },
        ...(CANCELLABLE_STATUSES.includes(d.status) ? [{ label: 'Annuler', icon: <X className="w-4 h-4" />, color: 'bg-red-600', onClick: onCancel }] : []),
      ] : []}
      rightActions={[
        ...(canWrite && d.status === 'draft' ? [{ label: 'Envoyer', icon: <Send className="w-4 h-4" />, color: 'bg-blue-600', onClick: onSend }] : []),
        ...(canWrite && d.status === 'accepted' ? [{ label: 'Convertir', icon: <ArrowRightCircle className="w-4 h-4" />, color: 'bg-emerald-600', onClick: onConvert }] : []),
      ]}
    >
      <button
        type="button"
        onClick={onNavigate}
        className={cn(
          'w-full text-left rounded-xl border-l-4 card',
          'hover:shadow-md transition-all',
          cfg.border,
        )}
      >
        <div className="p-4">
          {/* Row 1 : Ref + Status + Amount */}
          <div className="flex items-center justify-between gap-3 mb-2 min-w-0">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <span className="font-mono text-xs font-bold text-gold-400 truncate">{d.reference}</span>
              <DomainStatusBadge status={d.status} size="sm" />
            </div>
            <span className="text-base font-bold text-dark-50 tabular-nums shrink-0">
              {formatCents(d.total_cents)}
            </span>
          </div>

          {/* Row 2 : Client */}
          <p className="text-sm font-semibold text-dark-100 truncate mb-1.5">
            {d.customer_name || '—'}
          </p>

          {/* Row 3 : Dates */}
          <div className="flex items-center gap-3 text-xs text-dark-400 flex-wrap min-w-0">
            {d.event_date && (
              <span className="flex items-center gap-1 shrink-0">
                <CalendarCheck className="w-3 h-3 text-dark-500 shrink-0" />
                Événement {formatDate(d.event_date)}
              </span>
            )}
            {d.valid_until && (
              <>
                <span className="text-dark-600 hidden sm:inline">|</span>
                <span className="flex items-center gap-1 shrink-0">
                  <Clock className="w-3 h-3 text-dark-500 shrink-0" />
                  Validité {formatDate(d.valid_until)}
                </span>
              </>
            )}
          </div>
        </div>
      </button>
    </SwipeActions>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────
export default function DevisListPage() {
  const navigate = useNavigate({ from: '/devis/' })
  const { page, q, status } = useSearch({ strict: false }) as { page: number; q: string; status: DevisStatus | '' }
  const debouncedSearch = useDebounce(q, 300)
  const canWrite = useHasScope('devis:write')

  const setPage   = (p: number) => navigate({ search: (prev) => ({ ...prev, page: p }) })
  const setSearch = (v: string) => navigate({ search: (prev) => ({ ...prev, q: v || undefined, page: 1 }) })
  const setStatus = (v: DevisStatus | '') => navigate({ search: (prev) => ({ ...prev, status: v || undefined, page: 1 }) })

  const { cancel, duplicate, send, convertToReservation } = useDevisMutations()

  const { data, isLoading, isError, refetch } = useDevisList({
    skip: (page - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: status || undefined,
    search: debouncedSearch || undefined,
  })

  const { data: statsMap } = useDevisStats()

  const items: DevisListItem[] = data?.items || []
  const totalPages = Math.ceil((data?.total ?? 0) / PAGE_SIZE) || 1

  return (
    <div className="space-y-5">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Devis" subtitle={data?.total !== undefined ? `${data.total} devis` : 'Créez et suivez vos devis'} />
        {canWrite && (
          <button
            onClick={() => navigate({ to: '/devis/new' })}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Nouveau devis</span>
          </button>
        )}
      </div>

      {/* ── KPIs ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {([
          { label: 'Total', value: data?.total ?? '—', icon: <FileText className="w-5 h-5" />, bg: 'bg-dark-900', ring: 'ring-dark-600', text: 'text-dark-300', iconBg: 'bg-dark-900' },
          { label: 'Acceptés', value: statsMap?.accepted ?? '—', icon: <CheckCircle className="w-5 h-5" />, bg: 'bg-green-500/10', ring: 'ring-green-500/20', text: 'text-green-400', iconBg: 'bg-green-500/20' },
          { label: 'En attente', value: statsMap?.sent ?? '—', icon: <Send className="w-5 h-5" />, bg: 'bg-blue-500/10', ring: 'ring-blue-500/20', text: 'text-blue-400', iconBg: 'bg-blue-500/20' },
          { label: 'Expirés', value: statsMap?.expired ?? '—', icon: <AlertCircle className="w-5 h-5" />, bg: (statsMap?.expired ?? 0) > 0 ? 'bg-red-500/10' : 'bg-dark-900', ring: (statsMap?.expired ?? 0) > 0 ? 'ring-red-500/20' : 'ring-dark-600', text: (statsMap?.expired ?? 0) > 0 ? 'text-red-400' : 'text-dark-400', iconBg: (statsMap?.expired ?? 0) > 0 ? 'bg-red-500/20' : 'bg-dark-900' },
        ] as const).map((kpi) => (
          <div key={kpi.label} className={cn('rounded-xl p-4 ring-1', kpi.bg, kpi.ring)}>
            <div className="flex items-center gap-3">
              <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', kpi.iconBg, kpi.text)}>{kpi.icon}</div>
              <div>
                <p className={cn('text-2xl font-bold tabular-nums', kpi.text)}>{kpi.value}</p>
                <p className="text-[11px] text-dark-400 font-medium">{kpi.label}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Search ──────────────────────────────────────────────── */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
        <input
          type="text"
          placeholder="Référence, client…"
          value={q}
          onChange={(e) => setSearch(e.target.value)}
          className="input pl-9 w-full bg-dark-900 border-dark-600 focus:border-primary-500"
        />
      </div>

      {/* ── Status chips ────────────────────────────────────────── */}
      <div className="overflow-x-auto -mx-4 px-4">
        <div className="flex gap-1.5 pb-1 min-w-max">
          {STATUS_CHIPS.map((chip) => (
            <button
              key={chip.value}
              onClick={() => setStatus(chip.value)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all',
                status === chip.value
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

      {/* ── Cards ───────────────────────────────────────────────── */}
      <div className="space-y-2">
        {isError ? (
          <div className="card p-8 text-center space-y-4">
            <p className="text-red-400">Impossible de charger les devis.</p>
            <button onClick={() => refetch()} className="btn-secondary text-sm">Réessayer</button>
          </div>
        ) : isLoading ? (
          Array.from({ length: 6 }).map((_, i) => <DevisCardSkeleton key={i} />)
        ) : items.length === 0 ? (
          <div className="card p-8 text-center space-y-4">
            <p className="text-dark-400">Aucun devis{q || status ? ' pour ces critères' : ''}.</p>
            {!q && !status && canWrite && (
              <button onClick={() => navigate({ to: '/devis/new' })} className="btn-primary text-sm">Créer un devis</button>
            )}
          </div>
        ) : (
          items.map((d) => (
            <DevisCard
              key={d.id}
              d={d}
              onNavigate={() => navigate({ to: '/devis/$id', params: { id: String(d.id) } })}
              canWrite={canWrite}
              onDuplicate={() => duplicate.mutate(d.id)}
              onCancel={() => cancel.mutate(d.id)}
              onSend={() => send.mutate(d.id)}
              onConvert={() => navigate({ to: '/devis/$id', params: { id: String(d.id) }, search: { action: 'convert' } })}
            />
          ))
        )}
      </div>

      {/* ── Pagination ──────────────────────────────────────────── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-sm text-dark-400">Page {page}/{totalPages}</span>
          <div className="flex gap-2">
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1} className="btn-secondary disabled:opacity-30">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages} className="btn-secondary disabled:opacity-30">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
