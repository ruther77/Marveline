import { useNavigate } from '@tanstack/react-router'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { useAuthStore } from '@/stores/authStore'
import { cn, formatCents } from '@/lib/utils'
import {
  useDashboardStats,
  useDashboardUrgentAlert,
  useDashboardToday,
  useDashboardActivity,
} from '@/api/queries'
import type { TodayCard, ActivityItem } from '@/types/dashboard'
import {
  AlertTriangle,
  Search,
  Truck,
  RotateCcw,
  Plus,
  CalendarDays,
  CalendarCheck,
  CheckCircle,
  Euro,
  Package,
  Clock,
  ArrowRight,
} from 'lucide-react'

// ─── Skeletons ────────────────────────────────────────────────────────────────

function SkeletonLine({ w = 'w-full', h = 'h-3' }: { w?: string; h?: string }) {
  return <div className={cn('animate-pulse skel rounded', h, w)} />
}

function DashboardSkeleton() {
  return (
    <div className="space-y-4 px-4 pt-2">
      {/* greeting */}
      <div className="space-y-2">
        <SkeletonLine w="w-24" h="h-3" />
        <SkeletonLine w="w-48" h="h-6" />
      </div>
      {/* alert */}
      <div className="animate-pulse h-16 bg-dark-900 rounded-2xl border border-dark-600" />
      {/* search */}
      <div className="animate-pulse h-11 bg-dark-900 rounded-xl border border-dark-600" />
      {/* today cards */}
      <div className="flex gap-4 overflow-hidden">
        {[1, 2, 3].map(i => (
          <div key={i} className="animate-pulse shrink-0 w-40 h-24 bg-dark-900 rounded-xl border border-dark-600" />
        ))}
      </div>
      {/* quick actions */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {[1, 2, 3].map(i => (
          <div key={i} className="animate-pulse h-16 bg-dark-900 rounded-xl border border-dark-600" />
        ))}
      </div>
      {/* feed */}
      <div className="space-y-4">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="flex gap-4 items-start">
            <div className="animate-pulse w-2 h-2 rounded-full skel mt-1.5 shrink-0" />
            <div className="flex-1 space-y-1.5">
              <SkeletonLine w="w-40" h="h-3" />
              <SkeletonLine w="w-24" h="h-2.5" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Greeting ─────────────────────────────────────────────────────────────────

function Greeting({ name }: { name: string }) {
  const today = new Date()
  const dateStr = today.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
  // capitalize
  const label = dateStr.charAt(0).toUpperCase() + dateStr.slice(1)

  return (
    <div className="px-4 pt-4 pb-1">
      <p className="text-xs text-dark-400 mb-0.5">{label}</p>
      <h1 className="text-xl font-bold font-display">Bonjour, {name} 👋</h1>
    </div>
  )
}

// ─── Alerte urgente ───────────────────────────────────────────────────────────

function AlertUrgente() {
  const navigate = useNavigate()
  const { data: alert, isLoading } = useDashboardUrgentAlert()

  if (isLoading) return <div className="mx-4 animate-pulse h-16 bg-dark-900 rounded-2xl border border-dark-600" />
  if (!alert) return null

  return (
    <button
      className="mx-4 w-[calc(100%-2rem)] text-left rounded-2xl px-4 py-4 flex items-center gap-4 alert-box danger"
      onClick={() => navigate({ to: '/reservations/$id', params: { id: String(alert.reservation_id) } })}
    >
      <AlertTriangle className="w-5 h-5 text-danger shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-danger truncate">Retour à contrôler</p>
        <p className="text-xs text-muted2">{alert.reference} · {alert.customer_name}</p>
      </div>
      <ArrowRight className="w-4 h-4 text-danger shrink-0" />
    </button>
  )
}

// ─── Search surface ───────────────────────────────────────────────────────────

function SearchSurface() {
  const navigate = useNavigate()
  return (
    <button
      className="mx-4 w-[calc(100%-2rem)] flex items-center gap-2 px-4 h-11 card border border-dark-600 text-dark-400 text-sm hover:border-primary-400/50 transition-colors"
      onClick={() => navigate({ to: '/search', search: { q: '', types: [] } })}
    >
      <Search className="w-4 h-4 shrink-0" />
      <span>Rechercher client, réservation, produit…</span>
    </button>
  )
}

// ─── Today cards ──────────────────────────────────────────────────────────────

function TodayCardItem({ card }: { card: TodayCard }) {
  const navigate = useNavigate()
  const isDeparture = card.kind === 'departure'
  return (
    <button
      onClick={() => navigate({ to: '/reservations/$id', params: { id: String(card.reservation_id) } })}
      className={cn(
        'shrink-0 w-40 rounded-xl bg-dark-900 p-4 text-left border transition-colors',
        isDeparture
          ? 'border-blue-500/30 hover:border-blue-400/60'
          : 'border-orange-500/30 hover:border-orange-400/60',
      )}
    >
      <div className="flex items-center gap-1 mb-2">
        {isDeparture
          ? <Truck className="w-3 h-3 text-blue-400" />
          : <RotateCcw className="w-3 h-3 text-orange-400" />}
        <span className={cn('text-xs font-medium', isDeparture ? 'text-blue-400' : 'text-orange-400')}>
          {isDeparture ? 'Départ' : 'Retour'}
        </span>
        {card.hour && <span className="text-xs text-dark-400 ml-auto">{card.hour}</span>}
      </div>
      <p className="text-xs font-semibold truncate">{card.customer_name || card.reference}</p>
      <p className="text-xs text-dark-400 truncate">{card.reference}</p>
      <div className="flex items-center justify-between mt-2">
        <span className="text-xs text-dark-400">{card.articles_count} article{card.articles_count !== 1 ? 's' : ''}</span>
        {card.deposit_paid
          ? <CheckCircle className="w-3 h-3 text-green-400" />
          : <AlertTriangle className="w-3 h-3 text-yellow-400" />}
      </div>
    </button>
  )
}

function TodaySection() {
  const { data, isLoading } = useDashboardToday()

  if (isLoading) {
    return (
      <div className="px-4 space-y-2">
        <p className="text-xs font-semibold text-dark-400 uppercase tracking-wider">Aujourd'hui</p>
        <div className="flex gap-4 overflow-hidden">
          {[1, 2].map(i => <div key={i} className="animate-pulse shrink-0 w-40 h-24 bg-dark-900 rounded-xl border border-dark-600" />)}
        </div>
      </div>
    )
  }

  const cards = [
    ...(data?.departures ?? []),
    ...(data?.returns ?? []),
  ]

  if (!cards.length) return null

  return (
    <div className="space-y-2">
      <p className="px-4 text-xs font-semibold text-dark-400 uppercase tracking-wider">Aujourd'hui</p>
      <div className="flex gap-3 flex-wrap px-4 pb-1 lg:flex-nowrap lg:overflow-x-auto lg:scrollbar-hide">
        {cards.map((card) => (
          <TodayCardItem key={`${card.kind}-${card.reservation_id}`} card={card} />
        ))}
      </div>
    </div>
  )
}

// ─── Quick actions ────────────────────────────────────────────────────────────

function QuickActions() {
  const navigate = useNavigate()
  return (
    <div className="px-4 grid grid-cols-1 sm:grid-cols-3 gap-2">
      <button
        onClick={() => navigate({ to: '/devis/new' })}
        className="flex flex-col items-center justify-center gap-1 rounded-xl py-4 text-white text-xs font-medium transition-opacity hover:opacity-90"
        style={{ background: 'linear-gradient(135deg, var(--pink), var(--purple))' }}
      >
        <Plus className="w-5 h-5" />
        <span>Nouveau devis</span>
      </button>
      <button
        onClick={() => navigate({ to: '/planning' })}
        className="card flex flex-col items-center justify-center gap-1 rounded-xl py-4 text-xs font-medium transition-colors hover:border-primary-400/50"
      >
        <CalendarDays className="w-5 h-5 text-primary-400" />
        <span>Planning</span>
      </button>
      <button
        onClick={() => navigate({ to: '/reservations' })}
        className="card flex flex-col items-center justify-center gap-1 rounded-xl py-4 text-xs font-medium transition-colors hover:border-primary-400/50"
      >
        <CalendarCheck className="w-5 h-5 text-primary-400" />
        <span>Réservations</span>
      </button>
    </div>
  )
}

// ─── Activity feed ────────────────────────────────────────────────────────────

const ACTIVITY_COLORS: Record<ActivityItem['kind'], string> = {
  return_checked: 'bg-orange-400',
  invoice_paid: 'bg-green-400',
  deposit_received: 'bg-blue-400',
  quote_sent: 'bg-yellow-400',
  low_stock: 'bg-red-400',
  reservation_created: 'bg-primary-400',
}

function ActivityFeedSection() {
  const navigate = useNavigate()
  const { data, isLoading } = useDashboardActivity()

  if (isLoading) {
    return (
      <div className="px-4 space-y-4">
        <p className="text-xs font-semibold text-dark-400 uppercase tracking-wider">Activité récente</p>
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="flex gap-4 items-start">
            <div className="animate-pulse w-2 h-2 rounded-full skel mt-1.5 shrink-0" />
            <div className="flex-1 space-y-1.5">
              <div className="animate-pulse h-3 skel rounded w-40" />
              <div className="animate-pulse h-2.5 skel rounded w-24" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  const items = data?.items ?? []
  if (!items.length) return null

  return (
    <div className="px-4 space-y-2">
      <p className="text-xs font-semibold text-dark-400 uppercase tracking-wider">Activité récente</p>
      <div className="space-y-0 divide-y divide-dark-600">
        {items.map((item, idx) => (
          <button
            key={idx}
            className="w-full flex items-start gap-4 py-4 text-left hover:bg-dark-600/50 transition-colors rounded-lg px-2 -mx-2"
            onClick={() => {
              if (!item.link) return
              navigate({ to: item.link as never })
            }}
          >
            <span
              className={cn('w-2 h-2 rounded-full mt-1.5 shrink-0', ACTIVITY_COLORS[item.kind] ?? 'bg-dark-500')}
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm truncate">{item.label}</p>
              {item.sub_label && (
                <p className="text-xs text-dark-400 truncate">{item.sub_label}</p>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

// ─── KPI strip (compact, en bas) ─────────────────────────────────────────────

function KpiStrip() {
  const navigate = useNavigate()
  const { data: stats } = useDashboardStats()
  if (!stats) return null

  const kpis = [
    {
      icon: <CalendarCheck className="w-4 h-4 text-primary-400" />,
      label: 'Résa actives',
      value: stats.active_reservations,
      to: '/reservations',
      accent: 'border-primary-500/20',
    },
    {
      icon: <Euro className="w-4 h-4 text-red-400" />,
      label: 'En retard',
      value: formatCents(stats.overdue_amount_cents),
      to: '/finance/invoices',
      accent: stats.overdue_amount_cents > 0 ? 'border-red-500/30 bg-red-500/5' : 'border-dark-600',
    },
    {
      icon: <Truck className="w-4 h-4 text-blue-400" />,
      label: 'Départs',
      value: stats.scheduled_departures,
      to: '/operations',
      accent: 'border-blue-500/20',
    },
    {
      icon: <Package className="w-4 h-4 text-amber-400" />,
      label: 'Stock faible',
      value: stats.low_stock_products,
      to: '/stock/items',
      accent: stats.low_stock_products > 0 ? 'border-amber-500/30 bg-amber-500/5' : 'border-dark-600',
    },
    {
      icon: <RotateCcw className="w-4 h-4 text-orange-400" />,
      label: 'Retours',
      value: stats.scheduled_returns,
      to: '/operations',
      accent: 'border-orange-500/20',
    },
    {
      icon: <Clock className="w-4 h-4 text-dark-300" />,
      label: 'Brouillons',
      value: stats.draft_reservations,
      to: '/reservations',
      accent: 'border-dark-600',
    },
  ]

  return (
    <div className="px-4">
      <p className="text-xs font-semibold text-dark-400 uppercase tracking-wider mb-2">Vue d'ensemble</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {kpis.map((k) => (
          <button
            key={k.label}
            onClick={() => navigate({ to: k.to as never })}
            className={cn('card p-4 flex items-center gap-2 text-left hover:border-primary-400/30 transition-colors', k.accent)}
          >
            {k.icon}
            <div className="min-w-0">
              <p className="text-xs text-dark-400 truncate">{k.label}</p>
              <p className="text-sm font-bold">{k.value}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

// ─── FAB ──────────────────────────────────────────────────────────────────────

function FAB() {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => navigate({ to: '/devis/new' })}
      className="fixed z-40 w-14 h-14 rounded-full flex items-center justify-center shadow-lg active:scale-90 transition-all duration-200 will-change-transform lg:bottom-8"
      style={{
        bottom: 'calc(var(--nav-offset, 80px) + 16px)',
        right: '22px',
        background: 'linear-gradient(135deg, var(--pink), var(--purple))',
      }}
      aria-label="Nouveau devis"
    >
      <Plus className="w-6 h-6 text-white" />
    </button>
  )
}

// ─── Page principale ──────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuthStore()
  const { isLoading, error, refetch } = useDashboardStats()

  const firstName = user?.full_name?.split(' ')[0] || user?.email?.split('@')[0] || 'vous'

  if (isLoading) return <DashboardSkeleton />
  if (error) return (
    <div className="p-6 space-y-4">
      <Greeting name={firstName} />
      <ErrorState onRetry={() => refetch()} />
    </div>
  )

  return (
    <>
      <div className="space-y-6 pb-28">
        <Greeting name={firstName} />
        <AlertUrgente />
        <SearchSurface />
        <TodaySection />
        <QuickActions />
        <ActivityFeedSection />
        <KpiStrip />
      </div>
      <FAB />
    </>
  )
}
