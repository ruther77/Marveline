import { Users, TrendingUp, Gift, AlertTriangle, Download, Heart } from 'lucide-react'
import { useLoyaltyDashboard } from '@/api/queries/useLoyalty'
import { loyaltyApi } from '@/api/loyalty'
import { Link } from '@tanstack/react-router'
import { PageHeader } from '@/components/PageHeader'
import { ErrorState } from '@shared/components/ui/EmptyState'

const PROGRAM_ID = 1

function StatCard({ icon: Icon, label, value, sub, color = 'text-primary-400' }: {
  icon: typeof Users
  label: string
  value: string | number
  sub?: string
  color?: string
}) {
  return (
    <div className="card p-4 space-y-2">
      <div className="flex items-center gap-2 text-dark-400">
        <Icon className="w-4 h-4" />
        <span className="text-xs font-medium uppercase">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-dark-500">{sub}</p>}
    </div>
  )
}

export default function LoyaltyDashboardPage() {
  const { data, isLoading, error, refetch } = useLoyaltyDashboard(PROGRAM_ID)

  const handleExport = async (type: 'members' | 'transactions' | 'redemptions') => {
    const blob = await loyaltyApi.exportCsv(type, PROGRAM_ID)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `loyalty_${type}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (isLoading) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
        <PageHeader title="Fidélité" subtitle="Programme de fidélité client" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="card p-4 space-y-2 animate-pulse">
              <div className="h-3 w-20 bg-dark-100/10 rounded" />
              <div className="h-7 w-16 bg-dark-100/10 rounded" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
        <PageHeader title="Fidélité" subtitle="Programme de fidélité client" />
        <div className="card p-12 text-center">
          <Heart className="w-10 h-10 text-dark-400 mx-auto mb-4" />
          <p className="font-medium mb-1">Programme fidélité non configuré</p>
          <p className="text-sm text-dark-400 mb-4">
            Aucun programme actif. Configurez le programme de fidélité pour commencer.
          </p>
          {error && <ErrorState onRetry={() => refetch()} />}
        </div>
      </div>
    )
  }

  const redemptionPct = (data.redemption_rate * 100).toFixed(1)

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <PageHeader title="Fidélité" subtitle="Programme de fidélité client" />
        <button
          onClick={() => handleExport('members')}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs btn-secondary"
        >
          <Download className="w-3.5 h-3.5" /> Export membres
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Users} label="Membres" value={data.total_members} />
        <StatCard icon={Users} label="VIP" value={data.vip_members} color="text-gold-400" />
        <StatCard icon={TrendingUp} label="Points en circulation" value={data.total_points_in_circulation.toLocaleString()} />
        <StatCard icon={Gift} label="Taux rédemption" value={`${redemptionPct}%`} />
        <StatCard icon={TrendingUp} label="Points gagnés (mois)" value={data.points_earned_this_month.toLocaleString()} color="text-green-400" />
        <StatCard icon={Gift} label="Points utilisés (mois)" value={data.points_redeemed_this_month.toLocaleString()} />
        <StatCard icon={AlertTriangle} label="À risque" value={data.churn_risk_count} color="text-orange-400" sub="21-35j sans visite" />
        <StatCard icon={Users} label="Top parrains" value={data.top_referrers.length} />
      </div>

      {/* Navigation */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link to="/admin/loyalty-members" className="block">
          <div className="card p-4 hover:shadow-md transition-all cursor-pointer">
            <div className="flex items-center gap-3">
              <Users className="w-5 h-5 text-primary-400" />
              <div>
                <p className="font-medium text-sm">Membres</p>
                <p className="text-xs text-dark-400">Gérer les membres du programme</p>
              </div>
            </div>
          </div>
        </Link>
        <Link to="/admin/loyalty-rewards" className="block">
          <div className="card p-4 hover:shadow-md transition-all cursor-pointer">
            <div className="flex items-center gap-3">
              <Gift className="w-5 h-5 text-primary-400" />
              <div>
                <p className="font-medium text-sm">Catalogue récompenses</p>
                <p className="text-xs text-dark-400">Gérer les récompenses par palier</p>
              </div>
            </div>
          </div>
        </Link>
        <Link to="/admin/loyalty-flash" className="block">
          <div className="card p-4 hover:shadow-md transition-all cursor-pointer">
            <div className="flex items-center gap-3">
              <TrendingUp className="w-5 h-5 text-primary-400" />
              <div>
                <p className="font-medium text-sm">Offres flash</p>
                <p className="text-xs text-dark-400">Points x2, promotions temporaires</p>
              </div>
            </div>
          </div>
        </Link>
      </div>
    </div>
  )
}
