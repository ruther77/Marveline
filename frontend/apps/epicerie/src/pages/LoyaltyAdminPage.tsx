/**
 * Dashboard admin fidélité épicerie — L'Incontournable.
 * Spec §"Back-office" : nb membres, taux redemption, points en circulation, churn rate.
 */
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Users, TrendingUp, Gift, AlertTriangle, Download } from 'lucide-react'
import { massacorpApi } from '@/api'
import { normalizeError } from '@shared/errors/normalizer'

const PROGRAM_ID = 1

interface DashboardMetrics {
  total_members: number
  vip_members: number
  total_points_in_circulation: number
  redemption_rate: number
  points_earned_this_month: number
  points_redeemed_this_month: number
  churn_risk_count: number
  top_referrers: { member_id: number; first_name: string; referral_count: number }[]
}

function StatCard({ icon: Icon, label, value, sub, accent = false }: {
  icon: typeof Users
  label: string
  value: string | number
  sub?: string
  accent?: boolean
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-2">
      <div className="flex items-center gap-2 text-slate-400">
        <Icon className="w-4 h-4" />
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${accent ? 'text-emerald-600' : 'text-slate-900'}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400">{sub}</p>}
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-2 animate-pulse">
      <div className="h-3 w-20 bg-slate-100 rounded" />
      <div className="h-7 w-16 bg-slate-100 rounded" />
    </div>
  )
}

async function handleExport(type: 'members' | 'transactions' | 'redemptions') {
  const resp = await fetch(`/api/v1/loyalty/admin/export/${type}?program_id=${PROGRAM_ID}`, {
    credentials: 'include',
  })
  if (!resp.ok) throw new Error('Export échoué')
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `fidelite_${type}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function LoyaltyAdminPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['loyalty-dashboard', PROGRAM_ID],
    queryFn: () => massacorpApi.get<DashboardMetrics>(`/loyalty/admin/dashboard?program_id=${PROGRAM_ID}`),
    staleTime: 60_000,
  })

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Fidélité — L'Incontournable</h1>
          <p className="text-sm text-slate-500 mt-0.5">Programme fidélité restaurant & épicerie</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleExport('members')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-600"
          >
            <Download className="w-3.5 h-3.5" /> Membres CSV
          </button>
          <button
            onClick={() => handleExport('transactions')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-600"
          >
            <Download className="w-3.5 h-3.5" /> Transactions CSV
          </button>
        </div>
      </div>

      {/* KPIs */}
      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
          <p className="text-sm text-red-600 font-medium">{normalizeError(error).message || 'Erreur chargement dashboard'}</p>
          <button onClick={() => refetch()} className="mt-3 text-xs text-red-500 underline">Réessayer</button>
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard icon={Users} label="Membres" value={data.total_members} accent />
            <StatCard icon={Users} label="VIP" value={data.vip_members} sub="×1.5 points" />
            <StatCard icon={TrendingUp} label="Points en circulation" value={data.total_points_in_circulation.toLocaleString()} />
            <StatCard icon={Gift} label="Taux rédemption" value={`${(data.redemption_rate * 100).toFixed(1)} %`} />
            <StatCard icon={TrendingUp} label="Pts gagnés ce mois" value={data.points_earned_this_month.toLocaleString()} accent />
            <StatCard icon={Gift} label="Pts utilisés ce mois" value={data.points_redeemed_this_month.toLocaleString()} />
            <StatCard icon={AlertTriangle} label="À risque (churn)" value={data.churn_risk_count} sub="21-35j sans visite" />
            <StatCard icon={Users} label="Top parrains" value={data.top_referrers.length} />
          </div>

          {/* Top parrains */}
          {data.top_referrers.length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-3">Top parrains</h2>
              <div className="space-y-2">
                {data.top_referrers.slice(0, 5).map(r => (
                  <div key={r.member_id} className="flex items-center justify-between text-sm">
                    <span className="text-slate-800 font-medium">{r.first_name}</span>
                    <span className="text-emerald-600 font-semibold">{r.referral_count} filleul{r.referral_count > 1 ? 's' : ''}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Navigation admin */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link to="/fidelite/membres" className="block group">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 hover:border-emerald-300 hover:shadow-sm transition-all">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-emerald-50 rounded-xl flex items-center justify-center">
                <Users className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <p className="font-semibold text-sm text-slate-900">Membres</p>
                <p className="text-xs text-slate-400">Rechercher, ajuster, consulter</p>
              </div>
            </div>
          </div>
        </Link>
        <Link to="/fidelite/rewards" className="block group">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 hover:border-emerald-300 hover:shadow-sm transition-all">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-emerald-50 rounded-xl flex items-center justify-center">
                <Gift className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <p className="font-semibold text-sm text-slate-900">Catalogue récompenses</p>
                <p className="text-xs text-slate-400">Gérer les rewards par palier</p>
              </div>
            </div>
          </div>
        </Link>
        <Link to="/fidelite/rejoindre" className="block group">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 hover:border-emerald-300 hover:shadow-sm transition-all">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-emerald-50 rounded-xl flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <p className="font-semibold text-sm text-slate-900">Inscription client</p>
                <p className="text-xs text-slate-400">Page QR code comptoir</p>
              </div>
            </div>
          </div>
        </Link>
      </div>
    </div>
  )
}
