import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { AlertTriangle, Flame, Utensils, TrendingUp, TrendingDown } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import type {
  RestaurantDashboardStats,
  InstancePreparationRead,
  RupturesDashboard,
  ActiviteItem,
} from '@/types/restaurant-v2'

// FIN-VARIATION-01 : le backend ne renvoie pas encore `ca_variation_pct`
// (cf. spec §5.1). Ce cast permet de lire le champ dès qu'il sera ajouté au
// schema sans toucher ce fichier.
type StatsWithVariation = RestaurantDashboardStats & { ca_variation_pct?: number }

function fmtEur(cts: number): string {
  return (cts / 100).toFixed(2) + ' €'
}

function fmtHeure(iso: string): string {
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

// ─── HeroKPI — CA du jour en gros ────────────────────────────────────────────

function HeroKPI({ stats }: { stats?: RestaurantDashboardStats }) {
  const caCts = stats?.ca_cts ?? 0
  const couverts = stats?.nb_couverts ?? 0
  const ticketMoyen = stats?.ticket_moyen_cts ?? 0
  const variation = (stats as StatsWithVariation | undefined)?.ca_variation_pct
  const hasData = caCts > 0 || couverts > 0
  const variationUp = (variation ?? 0) >= 0
  const VariationIcon = variationUp ? TrendingUp : TrendingDown

  if (!hasData) {
    return (
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <div className="text-[13px] font-medium text-stone-500 mb-2">CA du jour</div>
        <div className="text-[28px] font-bold text-stone-300 mb-3">Pas encore de vente</div>
        <Link
          to="/salle"
          className="inline-flex items-center gap-2 h-11 px-4 bg-amber-600 text-white text-[14px] font-semibold rounded-xl hover:bg-amber-700"
        >
          Ouvrir une table
        </Link>
      </div>
    )
  }

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-6">
      <div className="text-[13px] font-medium text-stone-500 mb-2">CA du jour</div>
      <div className="flex items-baseline gap-3 flex-wrap mb-3">
        <div className="text-[40px] sm:text-[48px] font-bold text-stone-900 tracking-tight leading-none">
          {fmtEur(caCts)}
        </div>
        {variation != null && (
          <div className={`flex items-center gap-1 text-[14px] font-semibold ${
            variationUp ? 'text-emerald-600' : 'text-red-600'
          }`}>
            <VariationIcon className="h-4 w-4" />
            {variationUp ? '+' : ''}{variation.toFixed(0)}% vs hier
          </div>
        )}
      </div>
      <div className="flex items-center gap-4 text-[13px] text-stone-600 pt-3 border-t border-stone-100">
        <span><strong className="text-stone-900">{couverts}</strong> couverts</span>
        <span>·</span>
        <span><strong className="text-stone-900">{fmtEur(ticketMoyen)}</strong> ticket moyen</span>
      </div>
    </div>
  )
}

// ─── HubCard — carte drillable ───────────────────────────────────────────────

interface HubCardProps {
  to: string
  icon: React.ReactNode
  label: string
  value: string | number
  sub?: string
  variant?: 'default' | 'warn' | 'err'
}

function HubCard({ to, icon, label, value, sub, variant = 'default' }: HubCardProps) {
  const accent = variant === 'err' ? 'border-red-300 bg-red-50 hover:border-red-400'
    : variant === 'warn' ? 'border-amber-300 bg-amber-50 hover:border-amber-400'
    : 'border-stone-200 bg-white hover:border-amber-400'
  const iconBg = variant === 'err' ? 'bg-red-100 text-red-600'
    : variant === 'warn' ? 'bg-amber-100 text-amber-700'
    : 'bg-stone-100 text-stone-700'
  const valueColor = variant === 'err' ? 'text-red-600'
    : variant === 'warn' ? 'text-amber-700'
    : 'text-stone-900'

  return (
    <Link
      to={to}
      className={`group flex flex-col gap-3 p-5 border rounded-2xl transition-all min-h-[120px] ${accent}`}
    >
      <div className="flex items-center justify-between">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${iconBg}`}>
          {icon}
        </div>
        <span className="text-stone-300 group-hover:text-stone-500 text-[18px]">›</span>
      </div>
      <div>
        <div className={`text-[28px] font-bold leading-none ${valueColor}`}>{value}</div>
        <div className="text-[13px] font-medium text-stone-700 mt-1">{label}</div>
        {sub && <div className="text-[11.5px] text-stone-500 mt-0.5">{sub}</div>}
      </div>
    </Link>
  )
}

// ─── HubCards ────────────────────────────────────────────────────────────────

function HubCards({
  ruptures, marmites, commandesOuvertes,
}: {
  ruptures?: RupturesDashboard
  marmites: InstancePreparationRead[]
  commandesOuvertes: number
}) {
  const totalRuptures = (ruptures?.instances_vides.length ?? 0) + (ruptures?.ingredients_epuises.length ?? 0)

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <HubCard
        to="/stock"
        icon={<AlertTriangle className="h-5 w-5" />}
        label="Ruptures"
        value={totalRuptures}
        sub={totalRuptures === 0 ? 'Tout est en stock' : 'Nécessite action'}
        variant={totalRuptures > 0 ? 'err' : 'default'}
      />
      <HubCard
        to="/cuisine"
        icon={<Flame className="h-5 w-5" />}
        label="Marmites actives"
        value={marmites.length}
        sub={marmites.length === 0 ? 'Aucune en cuisine' : 'Voir la cuisine'}
      />
      <HubCard
        to="/salle"
        icon={<Utensils className="h-5 w-5" />}
        label="Tables actives"
        value={commandesOuvertes}
        sub={commandesOuvertes === 0 ? 'Aucune commande' : 'Voir la salle'}
      />
    </div>
  )
}

// ─── BandeauRuptures (détail sous hub) ───────────────────────────────────────

function BandeauRuptures({ ruptures }: { ruptures?: RupturesDashboard }) {
  const vides = ruptures?.instances_vides ?? []
  const epuises = ruptures?.ingredients_epuises ?? []
  const total = vides.length + epuises.length
  if (total === 0) return null

  return (
    <div className="border border-red-200 bg-red-50/50 rounded-2xl overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-3 border-b border-red-100">
        <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />
        <span className="text-red-700 font-semibold text-[14px] flex-1">
          Ruptures détectées
        </span>
        <Link to="/stock" className="text-[13px] text-red-700 hover:underline font-semibold min-h-[44px] flex items-center">
          Gérer →
        </Link>
      </div>
      <div className="flex flex-wrap gap-2 px-5 py-3">
        {vides.map(v => (
          <span key={v.instance_id} className="inline-flex items-center gap-1.5 text-[12px] bg-white border border-red-200 text-red-700 rounded-full px-3 py-1 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
            {v.type_preparation_nom} — {v.portions_restantes} portion{v.portions_restantes > 1 ? 's' : ''}
          </span>
        ))}
        {epuises.map(i => (
          <span key={i.ingredient_id} className="inline-flex items-center gap-1.5 text-[12px] bg-white border border-amber-200 text-amber-700 rounded-full px-3 py-1 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            {i.nom} — {i.stock_actuel_kg} {i.unite_stock}
          </span>
        ))}
      </div>
    </div>
  )
}

// ─── Timeline activité ──────────────────────────────────────────────────────

const STATUT_COLORS: Record<string, { dot: string; text: string; label: string }> = {
  PAYEE:   { dot: 'bg-emerald-500', text: 'text-emerald-700', label: 'Payée' },
  SERVIE:  { dot: 'bg-emerald-500', text: 'text-emerald-700', label: 'Servie' },
  OUVERTE: { dot: 'bg-blue-500',    text: 'text-blue-700',    label: 'Ouverte' },
  ANNULEE: { dot: 'bg-red-500',     text: 'text-red-600',     label: 'Annulée' },
}

function TimelineActivite({ items }: { items: ActiviteItem[] }) {
  return (
    <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
      <div className="px-5 py-3 border-b border-stone-100 flex items-center justify-between">
        <span className="text-[14px] font-semibold text-stone-900">Activité récente</span>
        <Link to="/historique" className="text-[12px] text-amber-600 hover:underline font-medium min-h-[44px] flex items-center">
          Historique complet →
        </Link>
      </div>
      {items.length === 0 ? (
        <div className="text-center py-8 px-5">
          <p className="text-[14px] font-semibold text-stone-700 mb-1">Premier service ?</p>
          <p className="text-[12px] text-stone-500 mb-3">Commencez par ouvrir une table ou lancer une marmite.</p>
          <div className="flex gap-2 justify-center">
            <Link to="/salle" className="inline-flex items-center gap-1.5 h-10 px-3 bg-amber-600 text-white text-[13px] font-semibold rounded-lg hover:bg-amber-700">
              Nouvelle table
            </Link>
            <Link to="/cuisine" className="inline-flex items-center gap-1.5 h-10 px-3 bg-stone-100 text-stone-700 text-[13px] font-semibold rounded-lg hover:bg-stone-200">
              Lancer marmite
            </Link>
          </div>
        </div>
      ) : (
        <div className="divide-y divide-stone-100">
          {items.slice(0, 5).map(item => {
            const c = STATUT_COLORS[item.statut] ?? { dot: 'bg-stone-400', text: 'text-stone-600', label: item.statut }
            return (
              <div key={item.commande_id} className="flex items-start gap-3 px-5 py-3">
                <div className={`w-2 h-2 rounded-full mt-[6px] shrink-0 ${c.dot}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-[13.5px] font-medium text-stone-900 truncate">
                    {item.table_numero ? `Table ${item.table_numero}` : `Commande #${item.commande_id}`}
                  </div>
                  <div className="text-[12px] text-stone-500 mt-0.5">
                    <span className={`font-semibold ${c.text}`}>{c.label}</span>
                    {' · '}{fmtHeure(item.date_ouverture)}
                    {item.total_cts > 0 && <> · {fmtEur(item.total_cts)}</>}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ─── Skeleton ────────────────────────────────────────────────────────────────

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-5 animate-pulse">
      <div className="bg-stone-200 rounded-2xl h-36" />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[0, 1, 2].map(i => <div key={i} className="bg-stone-200 rounded-2xl h-[120px]" />)}
      </div>
      <div className="bg-stone-200 rounded-2xl h-40" />
    </div>
  )
}

// ─── RestaurantDashboardPage ─────────────────────────────────────────────────

export default function RestaurantDashboardPage() {
  const today = new Date().toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long',
  })

  const { data: stats, isLoading: loadingStats } = useQuery({
    queryKey: ['restaurant-dashboard-stats'],
    queryFn: () => restaurantApi.getDashboardStats(),
    staleTime: 30_000,
  })

  const { data: marmitesData, isLoading: loadingMarmites } = useQuery({
    queryKey: ['restaurant-marmites'],
    queryFn: () => restaurantApi.getMarmites(),
    staleTime: 15_000,
  })

  const { data: rupturesData, isLoading: loadingRuptures } = useQuery({
    queryKey: ['restaurant-ruptures'],
    queryFn: () => restaurantApi.getRuptures(),
    staleTime: 30_000,
  })

  const { data: activiteData, isLoading: loadingActivite } = useQuery({
    queryKey: ['restaurant-activite'],
    queryFn: () => restaurantApi.getActiviteRecente(8),
    staleTime: 15_000,
  })

  const isLoading = loadingStats || loadingMarmites || loadingRuptures || loadingActivite
  const marmites = marmitesData?.items ?? []
  const commandesOuvertes = stats?.commandes_ouvertes ?? 0

  return (
    <div className="flex flex-col min-h-0 h-full bg-stone-50">
      {/* Header */}
      <div className="px-4 sm:px-7 py-4 border-b border-stone-200 bg-white">
        <h1 className="text-[18px] sm:text-[20px] font-bold text-stone-900 tracking-tight">Bonjour</h1>
        <p className="text-[13px] text-stone-500 mt-0.5 capitalize">{today}</p>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-7 py-5 flex flex-col gap-4">
        {isLoading ? (
          <DashboardSkeleton />
        ) : (
          <>
            <HeroKPI stats={stats} />
            <HubCards
              ruptures={rupturesData}
              marmites={marmites}
              commandesOuvertes={commandesOuvertes}
            />
            <BandeauRuptures ruptures={rupturesData} />
            <TimelineActivite items={activiteData?.items ?? []} />
          </>
        )}
      </div>
    </div>
  )
}
