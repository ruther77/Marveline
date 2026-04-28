// Route : /_massacorp/epicerie/dashboard
// Tableau de bord épicerie — stats stock + ruptures + alertes + activité récente

import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ShoppingCart, AlertTriangle } from 'lucide-react'
import { epicerieApi } from '@/api/epicerie'
import type { EpicerieStockSummary, EpicerieStockRead, EpicerieStockMovementRead } from '@/types/epicerie-v2'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

// ─── StatCard ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, accent = 'text-[#1d1d1f]' }: {
  label: string; value: string; sub: string; accent?: string
}) {
  return (
    <div className="bg-[#f5f5f7] border border-[#d2d2d7] rounded-md p-4">
      <div className="text-[11.5px] text-[#6e6e73] font-medium mb-1.5">{label}</div>
      <div className={`text-[22px] font-bold tracking-tight leading-none ${accent}`}>{value}</div>
      <div className="text-[11.5px] text-[#a1a1a6] mt-1.5">{sub}</div>
    </div>
  )
}

// ─── StatsGrid ────────────────────────────────────────────────────────────────

function StatsGrid({ stats }: { stats: EpicerieStockSummary | undefined }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <StatCard label="CA du jour" value="—" sub="Bientôt disponible" />
      <StatCard label="Transactions" value="—" sub="Bientôt disponible" />
      <StatCard label="Ticket moyen" value="—" sub="Bientôt disponible" />
      <StatCard label="Stock total" value={String(stats?.total_articles ?? '—')} sub="articles en stock" />
      <StatCard label="En rupture" value={String(stats?.nb_ruptures ?? '—')} sub="articles" accent={stats?.nb_ruptures ? 'text-[#991b1b]' : 'text-[#1d1d1f]'} />
      <StatCard label="Stock bas" value={String(stats?.nb_stock_bas ?? '—')} sub="articles" accent={stats?.nb_stock_bas ? 'text-[#92400e]' : 'text-[#1d1d1f]'} />
    </div>
  )
}

// ─── BandeauRuptures ─────────────────────────────────────────────────────────

function BandeauRuptures({ ruptures }: { ruptures: EpicerieStockRead[] }) {
  if (ruptures.length === 0) return null
  return (
    <div className="border-l-[3px] border-[#991b1b] bg-[rgba(153,27,27,.08)] rounded-md overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[rgba(153,27,27,.15)]">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-[#991b1b]" />
          <span className="text-[#991b1b] font-semibold text-sm">
            {ruptures.length} article{ruptures.length > 1 ? 's' : ''} en rupture de stock
          </span>
        </div>
        <Link to="/inventaire" className="text-xs text-[#059669] hover:underline font-medium">
          Voir inventaire
        </Link>
      </div>
      <div className="divide-y divide-[rgba(153,27,27,.1)]">
        {ruptures.map(r => (
          <div key={r.id} className="flex items-center justify-between px-4 py-2.5 gap-3">
            <span className="text-sm font-medium text-[#1d1d1f] flex-1 truncate">{r.designation}</span>
            <span className="text-xs text-[#6e6e73] shrink-0">{r.fournisseur_source ?? '—'}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── AlertesStockBas ─────────────────────────────────────────────────────────

function AlertesStockBas({ items }: { items: EpicerieStockRead[] }) {
  return (
    <div className="bg-[#f5f5f7] border border-[#d2d2d7] rounded-md overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#d2d2d7]">
        <span className="text-sm font-semibold text-[#1d1d1f]">Alertes stock bas</span>
        <Link to="/inventaire" className="text-xs text-[#059669] hover:underline font-medium">Gérer</Link>
      </div>
      {items.length === 0 ? (
        <p className="text-center text-xs text-[#a1a1a6] py-6">Aucune alerte</p>
      ) : (
        <div className="divide-y divide-[#d2d2d7]">
          {items.map(r => {
            const pct = r.seuil_alerte > 0 ? Math.min(100, Math.round((r.quantite / r.seuil_alerte) * 100)) : 0
            return (
              <div key={r.id} className="flex items-center gap-3 px-4 py-2.5">
                <span className="text-[13px] font-medium text-[#1d1d1f] w-[150px] shrink-0 truncate">{r.designation}</span>
                <div className="flex-1 h-[5px] bg-[#d2d2d7] rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${pct}%`, background: pct < 40 ? '#991b1b' : '#92400e' }} />
                </div>
                <span className="text-xs text-[#6e6e73] whitespace-nowrap">{r.quantite} / {r.seuil_alerte}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ─── ActiviteRecente ─────────────────────────────────────────────────────────

const ACTIVITY_COLORS: Record<string, string> = {
  VENTE: '#059669',
  ENTREE: '#4338ca',
  SORTIE: '#92400e',
  PERTE: '#991b1b',
  AJUSTEMENT: '#6d28d9',
  TRANSFERT_RESTAURANT: '#6d28d9',
}

function ActiviteRecente({ items }: { items: EpicerieStockMovementRead[] }) {
  return (
    <div className="bg-[#f5f5f7] border border-[#d2d2d7] rounded-md overflow-hidden">
      <div className="px-4 py-3 border-b border-[#d2d2d7]">
        <span className="text-sm font-semibold text-[#1d1d1f]">Activité récente</span>
      </div>
      {items.length === 0 ? (
        <p className="text-center text-xs text-[#a1a1a6] py-6">Aucune activité</p>
      ) : (
        <div className="divide-y divide-[#d2d2d7]">
          {items.map(m => (
            <div key={m.id} className="flex items-start gap-3 px-4 py-3">
              <div
                className="w-2 h-2 rounded-full mt-[5px] shrink-0"
                style={{ background: ACTIVITY_COLORS[m.type] ?? '#a1a1a6' }}
              />
              <div className="flex-1 min-w-0">
                <div className="text-[13.5px] font-medium text-[#1d1d1f] truncate">{m.produit_designation}</div>
                <div className="text-[12px] text-[#6e6e73] mt-0.5">
                  {m.type} · {fmtDate(m.date_mouvement)}
                  {m.created_by_name ? ` · ${m.created_by_name}` : ''}
                </div>
              </div>
              <span className={`text-[13.5px] font-semibold whitespace-nowrap ${m.signed_quantite > 0 ? 'text-[#1d7d4a]' : 'text-[#991b1b]'}`}>
                {m.signed_quantite > 0 ? `+${m.signed_quantite}` : String(m.signed_quantite)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── EpicerieDashboardPage ────────────────────────────────────────────────────

export default function EpicerieDashboardPage() {
  const today = new Date().toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })

  const { data: stats } = useQuery({
    queryKey: ['epicerie-stock-stats'],
    queryFn: () => epicerieApi.getStockStats(),
    staleTime: 30_000,
  })

  const { data: rupturesData } = useQuery({
    queryKey: ['epicerie-stock-ruptures'],
    queryFn: () => epicerieApi.listStock({ is_empty: true, per_page: 8 }),
    staleTime: 30_000,
  })

  const { data: alertesData } = useQuery({
    queryKey: ['epicerie-stock-bas'],
    queryFn: () => epicerieApi.listStock({ is_low: true, per_page: 5 }),
    staleTime: 30_000,
  })

  const { data: activiteData } = useQuery({
    queryKey: ['epicerie-mouvements-recents'],
    queryFn: () => epicerieApi.listMouvements({ per_page: 8 }),
    staleTime: 15_000,
  })

  return (
    <div className="flex flex-col min-h-0">
      <div className="px-7 pt-6 pb-4 border-b border-[#d2d2d7] bg-white flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-[22px] font-bold text-[#1d1d1f] tracking-tight">Tableau de bord</h1>
          <p className="text-[13px] text-[#6e6e73] mt-0.5 capitalize">Épicerie — {today}</p>
        </div>
        <Link
          to="/pos"
          className="flex items-center gap-1.5 px-3.5 py-2 bg-[#059669] text-white text-[13px] font-semibold rounded-md hover:opacity-90"
        >
          <ShoppingCart className="h-4 w-4" />
          Ouvrir POS
        </Link>
      </div>

      <div className="flex-1 overflow-y-auto px-7 py-5 flex flex-col gap-4">
        <StatsGrid stats={stats} />
        <BandeauRuptures ruptures={rupturesData?.items ?? []} />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <AlertesStockBas items={alertesData?.items ?? []} />
          <ActiviteRecente items={activiteData?.items ?? []} />
        </div>
      </div>
    </div>
  )
}
