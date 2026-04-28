import { Link } from '@tanstack/react-router'
import { RefreshCw, Truck, RotateCcw, Activity, AlertTriangle, Weight, Package, MapPin, ArrowRight, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { usePlanningToday } from '@/api/queries/usePlanning'
import type { PlanningTodayReservation } from '@/types/planning'

const STATUS_LABELS: Record<string, string> = {
  confirmed: 'Confirmé',
  confirmed_risk: 'Risque',
  pre_check: 'Pré-check',
  delivered: 'Livré',
  extended: 'Prolongé',
}

const STATUS_BADGE: Record<string, string> = {
  confirmed:      'bg-green-500/10 text-green-400 border-green-500/30',
  confirmed_risk: 'bg-red-500/10 text-red-400 border-red-500/30',
  pre_check:      'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  delivered:      'bg-blue-500/10 text-blue-400 border-blue-500/30',
  extended:       'bg-amber-500/10 text-amber-400 border-amber-500/30',
}

// ─── KPI Card ────────────────────────────────────────────────────────────────

function KpiCard({ label, value, color, border, icon: Icon }: {
  label: string; value: number; color: string; border: string; icon: React.ElementType
}) {
  return (
    <div className={cn('rounded-2xl px-4 py-5 border transition-colors', border)}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={cn('w-4 h-4', color)} />
        <span className="text-xs text-dark-400 font-medium">{label}</span>
      </div>
      <p className={cn('text-3xl font-bold font-display', color)}>{value}</p>
    </div>
  )
}

// ─── Reservation Row ─────────────────────────────────────────────────────────

function ReservationRow({ r }: { r: PlanningTodayReservation }) {
  return (
    <Link
      to="/reservations/$id"
      params={{ id: String(r.id) }}
      className="flex items-center gap-4 px-4 py-4 hover:bg-dark-800/50 transition-colors group"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="font-semibold text-sm text-white truncate">{r.customer_name || r.reference}</p>
          <span className={cn(
            'text-[10px] px-2 py-0.5 rounded-full border shrink-0',
            STATUS_BADGE[r.status] ?? 'bg-dark-800 text-dark-300 border-dark-600',
          )}>
            {STATUS_LABELS[r.status] ?? r.status}
          </span>
        </div>
        <p className="text-xs text-dark-500 mt-0.5">{r.reference}{r.event_name ? ` · ${r.event_name}` : ''}</p>

        {/* Badges logistique */}
        {(r.total_weight_grams || r.container_count || r.delivery_zone_name) && (
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {r.total_weight_grams != null && r.total_weight_grams > 0 && (
              <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-dark-800 text-dark-300 border border-dark-700">
                <Weight size={10} />{(r.total_weight_grams / 1000).toFixed(0)} kg
              </span>
            )}
            {(r.container_count ?? 0) > 0 && (
              <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-dark-800 text-dark-300 border border-dark-700">
                <Package size={10} />{r.container_count} bac{(r.container_count ?? 0) > 1 ? 's' : ''}
              </span>
            )}
            {r.delivery_zone_name && (
              <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-dark-800 text-dark-300 border border-dark-700">
                <MapPin size={10} />{r.delivery_zone_name}
              </span>
            )}
          </div>
        )}
      </div>
      <ArrowRight className="w-4 h-4 text-dark-600 group-hover:text-dark-300 transition-colors shrink-0" />
    </Link>
  )
}

// ─── Section ─────────────────────────────────────────────────────────────────

function Section({ title, icon: Icon, items, emptyLabel, color }: {
  title: string; icon: React.ElementType; items: PlanningTodayReservation[]; emptyLabel: string; color: string
}) {
  if (items.length === 0) return null

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 px-1">
        <Icon className={cn('w-4 h-4', color)} />
        <p className="text-xs font-semibold text-dark-400 uppercase tracking-wider">{title}</p>
        <span className={cn('text-xs font-bold px-2 py-0.5 rounded-full ml-auto', color.replace('text-', 'bg-').replace('400', '500/10'))}>
          {items.length}
        </span>
      </div>
      <div className="card overflow-hidden divide-y divide-dark-700/50">
        {items.map((r) => <ReservationRow key={r.id} r={r} />)}
      </div>
    </div>
  )
}

// ─── Skeleton ────────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="space-y-2">
        <div className="h-3 bg-dark-800 rounded w-24" />
        <div className="h-7 bg-dark-800 rounded w-40" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-2xl border border-dark-700 p-5 space-y-3">
            <div className="h-3 bg-dark-800 rounded w-20" />
            <div className="h-8 bg-dark-800 rounded w-12" />
          </div>
        ))}
      </div>
      <div className="card divide-y divide-dark-700/50">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 p-4">
            <div className="flex-1 space-y-2">
              <div className="h-3 bg-dark-800 rounded w-40" />
              <div className="h-2 bg-dark-800 rounded w-56" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function PlanningTodayPage() {
  const { data, isLoading, refetch, isFetching } = usePlanningToday()

  if (isLoading) return <Skeleton />

  const today = data ? new Date(data.date) : new Date()
  const dateLabel = today.toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs text-dark-400">{dateLabel.charAt(0).toUpperCase() + dateLabel.slice(1)}</p>
          <h1 className="text-xl font-bold font-display text-white flex items-center gap-2 min-w-0">
            <Clock className="w-5 h-5 text-primary-400" />
            Jour J
          </h1>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-dark-600 text-dark-400 hover:text-white hover:border-dark-400 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={12} className={isFetching ? 'animate-spin' : ''} />
          Actualiser
        </button>
      </div>

      {data && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KpiCard label="Départs" value={data.total_departures} color="text-blue-400" border="border-blue-500/20 bg-blue-500/5" icon={Truck} />
            <KpiCard label="Retours" value={data.total_returns} color="text-green-400" border="border-green-500/20 bg-green-500/5" icon={RotateCcw} />
            <KpiCard label="En cours" value={data.total_active} color="text-amber-400" border="border-amber-500/20 bg-amber-500/5" icon={Activity} />
            <KpiCard label="Retards" value={data.total_overdue} color={data.total_overdue > 0 ? 'text-red-400' : 'text-dark-500'} border={data.total_overdue > 0 ? 'border-red-500/30 bg-red-500/10' : 'border-dark-700'} icon={AlertTriangle} />
          </div>

          {/* Sections */}
          <div className="space-y-6">
            <Section title="Départs" icon={Truck} items={data.departures} emptyLabel="Aucun départ" color="text-blue-400" />
            <Section title="Retours attendus" icon={RotateCcw} items={data.returns_today} emptyLabel="Aucun retour" color="text-green-400" />
            <Section title="En cours" icon={Activity} items={data.active} emptyLabel="" color="text-amber-400" />
            <Section title="Retards" icon={AlertTriangle} items={data.overdue} emptyLabel="" color="text-red-400" />
          </div>

          {/* Empty state */}
          {data.total_departures === 0 && data.total_returns === 0 && data.total_active === 0 && (
            <div className="card p-12 text-center">
              <Clock size={40} className="mx-auto mb-3 text-dark-600" />
              <p className="text-dark-400 text-sm">Journée calme — aucune opération prévue.</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
