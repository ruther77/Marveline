import { useAuthStore } from '@/stores/authStore'
import { StatCard } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/Breadcrumb'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/api/dashboard'
import { useNavigate } from 'react-router-dom'
import {
  CalendarCheck,
  FileText,
  AlertTriangle,
  Package,
  Truck,
  RotateCcw,
  Euro,
  Loader2,
  Clock,
} from 'lucide-react'
import { cn } from '@/lib/utils'

function formatCents(cents: number): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
  }).format(cents / 100)
}

export default function DashboardPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: dashboardApi.getStats,
    refetchInterval: 60_000,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Bienvenue, ${user?.full_name || user?.email || 'Utilisateur'}`}
        subtitle="Tableau de bord Marveline"
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
        </div>
      ) : stats ? (
        <>
          {/* Row 1: Reservations + CA */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Reservations actives"
              value={stats.active_reservations}
              icon={<CalendarCheck className="w-5 h-5" />}
              className="cursor-pointer"
              onClick={() => navigate('/events')}
            />
            <StatCard
              title="Brouillons"
              value={stats.draft_reservations}
              icon={<Clock className="w-5 h-5" />}
              className="cursor-pointer"
              onClick={() => navigate('/events')}
            />
            <StatCard
              title="CA du mois"
              value={formatCents(stats.monthly_revenue_cents)}
              icon={<Euro className="w-5 h-5" />}
            />
            <StatCard
              title="Produits actifs"
              value={stats.total_products}
              icon={<Package className="w-5 h-5" />}
              className="cursor-pointer"
              onClick={() => navigate('/products')}
            />
          </div>

          {/* Row 2: Factures */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard
              title="Factures en retard"
              value={stats.overdue_invoices}
              icon={<AlertTriangle className={cn('w-5 h-5', stats.overdue_invoices > 0 && 'text-red-400')} />}
              className={cn('cursor-pointer', stats.overdue_invoices > 0 && 'border-red-500/30')}
              onClick={() => navigate('/invoices')}
            />
            <StatCard
              title="Montant en retard"
              value={formatCents(stats.overdue_amount_cents)}
              icon={<Euro className={cn('w-5 h-5', stats.overdue_amount_cents > 0 && 'text-red-400')} />}
              className={cn(stats.overdue_amount_cents > 0 && 'border-red-500/30')}
            />
            <StatCard
              title="Factures non payees"
              value={stats.unpaid_invoices}
              icon={<FileText className="w-5 h-5" />}
              className="cursor-pointer"
              onClick={() => navigate('/invoices')}
            />
          </div>

          {/* Row 3: Mouvements + Stock */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Departs programmes"
              value={stats.scheduled_departures}
              icon={<Truck className="w-5 h-5" />}
              className="cursor-pointer"
              onClick={() => navigate('/inventory/movements')}
            />
            <StatCard
              title="Retours programmes"
              value={stats.scheduled_returns}
              icon={<RotateCcw className="w-5 h-5" />}
              className="cursor-pointer"
              onClick={() => navigate('/inventory/movements')}
            />
            <StatCard
              title="Mouvements en retard"
              value={stats.late_movements}
              icon={<AlertTriangle className={cn('w-5 h-5', stats.late_movements > 0 && 'text-orange-400')} />}
              className={cn(stats.late_movements > 0 && 'border-orange-500/30')}
            />
            <StatCard
              title="Stock faible"
              value={stats.low_stock_products}
              icon={<Package className={cn('w-5 h-5', stats.low_stock_products > 0 && 'text-yellow-400')} />}
              className={cn('cursor-pointer', stats.low_stock_products > 0 && 'border-yellow-500/30')}
              onClick={() => navigate('/inventory/stock')}
            />
          </div>
        </>
      ) : (
        <div className="text-center py-12 text-dark-400">
          Impossible de charger les statistiques
        </div>
      )}
    </div>
  )
}
