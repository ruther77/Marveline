import { useEffect } from 'react'
import { Outlet, Link, useNavigate, useRouterState } from '@tanstack/react-router'
import { Sun, Moon } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@shared/lib/utils'
import { useMassaCorpAuthStore } from '@shared/stores/massacorpAuthStore'
import { massacorpApi } from '@/api'
import { epicerieApi } from '@/api/epicerie'

// ── Nav items ────────────────────────────────────────────────────────────────

interface NavItem {
  label: string
  href: string
  icon: React.ReactNode
  shortLabel?: string
  badge?: number
}

const IcoDashboard = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
  </svg>
)
const IcoInventaire = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="2"/><path d="m9 12 2 2 4-4"/>
  </svg>
)
const IcoPos = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
  </svg>
)
const IcoFournisseurs = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
)
const IcoHistorique = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
  </svg>
)
const IcoReception = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12H19M12 5l7 7-7 7"/>
  </svg>
)
const IcoTransferts = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="m17 1 4 4-4 4"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><path d="m7 23-4-4 4-4"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>
  </svg>
)
const IcoEtl = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
  </svg>
)
const IcoCategories = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
  </svg>
)
const IcoConflits = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
)
const IcoFidelite = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
  </svg>
)

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard',           href: '/dashboard',     icon: <IcoDashboard />,    shortLabel: 'Accueil' },
  { label: 'Inventaire',          href: '/inventaire',    icon: <IcoInventaire />,   shortLabel: 'Stock' },
  { label: 'Point de vente',      href: '/pos',           icon: <IcoPos />,          shortLabel: 'Caisse' },
  { label: 'Fournisseurs',        href: '/fournisseurs',  icon: <IcoFournisseurs />, shortLabel: 'Fourn.' },
  { label: 'Historique ventes',   href: '/historique',    icon: <IcoHistorique />,   shortLabel: 'Ventes' },
  { label: 'Réception commandes', href: '/reception',     icon: <IcoReception />,    shortLabel: 'Récep.' },
  { label: 'Transferts internes', href: '/transferts',    icon: <IcoTransferts />,   shortLabel: 'Transf.' },
  { label: 'Demandes restaurant', href: '/transferts-demandes', icon: <IcoTransferts />, shortLabel: 'Demandes' },
  { label: 'Import factures',    href: '/etl-imports',   icon: <IcoEtl />,          shortLabel: 'Import' },
  { label: 'Conflits ETL',       href: '/etl-conflits',  icon: <IcoConflits />,     shortLabel: 'Conflits' },
  { label: 'Marges',             href: '/marges',        icon: <IcoEtl />,          shortLabel: 'Marges' },
  { label: 'Catégories',        href: '/categories',    icon: <IcoCategories />,   shortLabel: 'Catég.' },
  { label: 'Fidélité',          href: '/fidelite',      icon: <IcoFidelite />,     shortLabel: 'Fidél.' },
]

// Bottom nav mobile — 5 items max
const BOTTOM_NAV = NAV_ITEMS.slice(0, 5)

// ── Sidebar link ─────────────────────────────────────────────────────────────

function SidebarLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const active = pathname === item.href || pathname.startsWith(item.href + '/')
  return (
    <Link
      to={item.href}
      className={cn(
        'flex items-center gap-3 px-4 py-2.5 text-[13.5px] font-medium',
        'border-l-2 transition-colors',
        active
          ? 'text-emerald-600 border-l-emerald-600 bg-emerald-50/60 font-semibold [&>svg]:opacity-100'
          : 'text-slate-600 border-l-transparent hover:bg-slate-100 hover:text-slate-900 [&>svg]:opacity-70',
      )}
    >
      {item.icon}
      {item.label}
      {item.badge != null && item.badge > 0 && (
        <span className="ml-auto min-w-[18px] h-[18px] px-1 rounded-full bg-amber-500 text-white text-[10px] font-bold flex items-center justify-center">
          {item.badge > 99 ? '99+' : item.badge}
        </span>
      )}
    </Link>
  )
}

// ── Bottom nav item ──────────────────────────────────────────────────────────

function BottomNavItem({ item, pathname }: { item: NavItem; pathname: string }) {
  const active = pathname === item.href || pathname.startsWith(item.href + '/')
  return (
    <Link
      to={item.href}
      className={cn(
        'flex flex-col items-center gap-0.5 py-1.5 min-w-[56px]',
        active ? 'text-emerald-600' : 'text-slate-400',
      )}
    >
      <span className={cn('[&>svg]:w-5 [&>svg]:h-5', active && 'scale-110')}>{item.icon}</span>
      <span className="text-[10px] font-medium">{item.shortLabel || item.label}</span>
    </Link>
  )
}

// ── Sidebar (tablette paysage / desktop) ─────────────────────────────────────

function Sidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const nav = useNavigate()

  const { data: conflictStats } = useQuery({
    queryKey: ['etl-conflicts-stats'],
    queryFn: () => massacorpApi.get<{ pending: number }>('/admin/etl/conflicts/stats'),
    staleTime: 60_000,
    refetchInterval: 120_000,
  })

  const { data: demandesStats } = useQuery({
    queryKey: ['epicerie-transfer-requests-pending-count'],
    queryFn: () => epicerieApi.listTransferRequests({ status: 'PENDING', per_page: 1 }),
    staleTime: 60_000,
    refetchInterval: 90_000,
  })

  const navItems = NAV_ITEMS.map(item => {
    if (item.href === '/etl-conflits' && conflictStats?.pending) return { ...item, badge: conflictStats.pending }
    if (item.href === '/transferts-demandes' && demandesStats?.total) return { ...item, badge: demandesStats.total }
    return item
  })

  return (
    <aside className="w-[240px] flex-shrink-0 flex flex-col sticky top-0 h-screen overflow-y-auto bg-slate-50 border-r border-slate-200">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-slate-200">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-emerald-600">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
            <line x1="3" y1="6" x2="21" y2="6"/>
            <path d="M16 10a4 4 0 0 1-8 0"/>
          </svg>
        </div>
        <span className="text-[15px] font-bold tracking-tight text-slate-900">Epicerie</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2">
        {navItems.map((item) => (
          <SidebarLink key={item.href} item={item} pathname={pathname} />
        ))}
      </nav>

      {/* Footer */}
      <div className="mt-auto px-4 py-3 border-t border-slate-200">
        <button
          onClick={() => {
            useMassaCorpAuthStore.getState().logout()
            nav({ to: '/login' })
          }}
          className="flex items-center gap-2 w-full px-2 py-2 rounded-md text-[12.5px] text-slate-500 hover:bg-red-50 hover:text-red-600 transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          Deconnexion
        </button>
      </div>
    </aside>
  )
}

// ── Bottom nav (téléphone / tablette portrait) ───────────────────────────────

function BottomNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })

  return (
    <nav className="fixed bottom-0 inset-x-0 bg-white border-t border-slate-200 flex justify-around items-center pb-[env(safe-area-inset-bottom)] z-40 lg:hidden">
      {BOTTOM_NAV.map((item) => (
        <BottomNavItem key={item.href} item={item} pathname={pathname} />
      ))}
    </nav>
  )
}

// ── Layout ────────────────────────────────────────────────────────────────────

export default function EpicerieLayout() {
  const navigate = useNavigate()

  // Session expirée (REPLAY_DETECTED ou refresh échoué) → redirect login
  useEffect(() => {
    const handler = () => navigate({ to: '/login' })
    window.addEventListener('massacorp:session-expired', handler)
    return () => window.removeEventListener('massacorp:session-expired', handler)
  }, [navigate])

  return (
    <div className="flex min-h-screen bg-white text-slate-900">
      {/* Sidebar — tablette paysage + desktop */}
      <div className="hidden lg:flex">
        <Sidebar />
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0 overflow-y-auto pb-16 lg:pb-0">
        <Outlet />
      </div>

      {/* Bottom nav — mobile + tablette portrait */}
      <BottomNav />
    </div>
  )
}
