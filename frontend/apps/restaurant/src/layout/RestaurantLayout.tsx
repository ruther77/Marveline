import { useState, useEffect } from 'react'
import { Outlet, Link, useNavigate, useRouterState } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import { cn } from '@shared/lib/utils'
import { useKdsWebSocket } from '@/hooks/useKdsWebSocket'
import { BuzzerAlert } from '@/components'
import { useMassaCorpAuthStore } from '@shared/stores/massacorpAuthStore'
import { massacorpTokenStore } from '@shared/stores/massacorpTokenStore'
import { useRestaurantScopes } from '@/hooks/useRestaurantScopes'

// ── Nav items ────────────────────────────────────────────────────────────────

type NavScope = 'service' | 'gestion'

interface NavItem {
  label: string
  href: string
  icon: React.ReactNode
  shortLabel?: string
  /** 'service' = visible par staff + manager. 'gestion' = manager uniquement. */
  visibility: NavScope
}

const IcoDashboard = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
  </svg>
)
const IcoSalle = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9h18"/><path d="M3 15h18"/><path d="M8 9v6"/><path d="M16 9v6"/><rect x="2" y="5" width="20" height="14" rx="2"/>
  </svg>
)
const IcoCuisine = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M15 11h.01"/><path d="M11 15h.01"/><path d="M16 16h.01"/><path d="m2 16 20 6-6-20A20 20 0 0 0 2 16"/><path d="M5.71 17.11a17.04 17.04 0 0 1 11.4-11.4"/>
  </svg>
)
const IcoBar = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M8 22h8"/><path d="M12 11v11"/><path d="m19 3-7 8-7-8z"/>
  </svg>
)
const IcoIngredients = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
  </svg>
)
const IcoHistorique = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
  </svg>
)

const IcoMenu = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 19h16"/><path d="M4 15h16"/><path d="M4 11h16"/><path d="M4 7h16"/>
  </svg>
)
const IcoCatalogue = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
    <polyline points="3.29 7 12 12 20.71 7"/><line x1="12" y1="22" x2="12" y2="12"/>
  </svg>
)
const IcoPreparations = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 12h20"/><path d="M6 12v4a6 6 0 0 0 12 0v-4"/><path d="M6 8a6 6 0 0 1 12 0"/><path d="M12 2v2"/>
  </svg>
)
const IcoDemandes = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="13" y2="17"/>
  </svg>
)
const IcoFidelite = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
  </svg>
)

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard',   href: '/dashboard',  icon: <IcoDashboard />,   shortLabel: 'Accueil',   visibility: 'gestion' },
  { label: 'Salle',       href: '/salle',      icon: <IcoSalle />,       shortLabel: 'Salle',     visibility: 'service' },
  { label: 'Cuisine',     href: '/cuisine',    icon: <IcoCuisine />,     shortLabel: 'Cuisine',   visibility: 'service' },
  { label: 'Bar',         href: '/bar',        icon: <IcoBar />,         shortLabel: 'Bar',       visibility: 'service' },
  { label: 'Stock',       href: '/stock',      icon: <IcoIngredients />, shortLabel: 'Stock',     visibility: 'gestion' },
  { label: 'Carte',       href: '/menu',       icon: <IcoMenu />,        shortLabel: 'Carte',     visibility: 'gestion' },
  { label: 'Historique',  href: '/historique', icon: <IcoHistorique />,  shortLabel: 'Histo.',    visibility: 'service' },
]

// Sidebar admin uniquement — pas dans la bottom nav mobile
const SIDEBAR_EXTRA: NavItem[] = [
  { label: 'Catalogue',    href: '/catalogue',    icon: <IcoCatalogue />,    shortLabel: 'Catalogue', visibility: 'gestion' },
  { label: 'Préparations', href: '/preparations', icon: <IcoPreparations />, shortLabel: 'Prép.',     visibility: 'gestion' },
  { label: 'Mes demandes', href: '/mes-demandes', icon: <IcoDemandes />,     shortLabel: 'Demandes',  visibility: 'gestion' },
  { label: 'Fidélité',     href: '/fidelite',     icon: <IcoFidelite />,     shortLabel: 'Fidél.',    visibility: 'gestion' },
]

// Bottom nav mobile — items principaux selon rôle
const MANAGER_BOTTOM_HREFS = ['/dashboard', '/salle', '/stock', '/menu']
const STAFF_BOTTOM_HREFS = ['/salle', '/cuisine', '/bar', '/historique']

function visibleItems(items: NavItem[], canEdit: boolean): NavItem[] {
  return items.filter(i => canEdit || i.visibility === 'service')
}

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
          ? 'text-amber-600 border-l-amber-600 bg-amber-50/60 font-semibold [&>svg]:opacity-100'
          : 'text-stone-600 border-l-transparent hover:bg-stone-100 hover:text-stone-900 [&>svg]:opacity-70',
      )}
    >
      {item.icon}
      {item.label}
    </Link>
  )
}

// ── Bottom nav item (gros boutons tactiles pour serveurs) ────────────────────

function BottomNavItem({ item, pathname }: { item: NavItem; pathname: string }) {
  const active = pathname === item.href || pathname.startsWith(item.href + '/')
  return (
    <Link
      to={item.href}
      className={cn(
        'flex flex-col items-center gap-0.5 py-1.5 min-w-[52px] min-h-[44px]',
        active ? 'text-amber-600' : 'text-stone-400',
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
  const { canEdit, isStaff } = useRestaurantScopes()

  const serviceItems = NAV_ITEMS.filter(i => i.visibility === 'service')
  const gestionItems = canEdit
    ? [...NAV_ITEMS.filter(i => i.visibility === 'gestion'), ...SIDEBAR_EXTRA]
    : []

  return (
    <aside className="w-[220px] flex-shrink-0 flex flex-col sticky top-0 h-screen overflow-y-auto bg-stone-50 border-r border-stone-200">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-stone-200">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-amber-600">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 11h.01"/><path d="M11 15h.01"/><path d="M16 16h.01"/><path d="m2 16 20 6-6-20A20 20 0 0 0 2 16"/>
          </svg>
        </div>
        <span className="text-[15px] font-bold tracking-tight text-stone-900">Restaurant</span>
        {isStaff && !canEdit && (
          <span className="ml-auto text-[9px] font-semibold uppercase tracking-wider text-stone-400 bg-stone-200 px-1.5 py-0.5 rounded">
            Service
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2">
        <p className="px-4 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-widest text-stone-400">Service</p>
        {serviceItems.map(item => (
          <SidebarLink key={item.href} item={item} pathname={pathname} />
        ))}
        {gestionItems.length > 0 && (
          <>
            <p className="px-4 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-widest text-stone-400">Gestion</p>
            {gestionItems.map(item => (
              <SidebarLink key={item.href} item={item} pathname={pathname} />
            ))}
          </>
        )}
      </nav>

      {/* Footer — verrouiller + déconnexion */}
      <div className="mt-auto px-4 py-3 border-t border-stone-200 space-y-1">
        <button
          onClick={() => nav({ to: '/login' })}
          className="flex items-center gap-2 w-full px-2 py-2 rounded-md text-[12.5px] text-stone-500 hover:bg-stone-200 hover:text-stone-900 transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          Verrouiller
        </button>
        <button
          onClick={() => {
            useMassaCorpAuthStore.getState().logout()
            massacorpTokenStore.clear()
            nav({ to: '/login' })
          }}
          className="flex items-center gap-2 w-full px-2 py-2 rounded-md text-[12.5px] text-stone-500 hover:bg-red-50 hover:text-red-600 transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          Deconnexion
        </button>
      </div>
    </aside>
  )
}

// ── More drawer (bottom sheet) ───────────────────────────────────────────────

function MoreDrawer({ open, onClose, pathname, drawerItems }: { open: boolean; onClose: () => void; pathname: string; drawerItems: NavItem[] }) {
  const nav = useNavigate()
  if (!open) return null

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30" onClick={onClose} />
      <div className="fixed bottom-0 inset-x-0 z-50 bg-white rounded-t-2xl border-t border-stone-200 pb-[env(safe-area-inset-bottom)]">
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full bg-stone-300" />
        </div>
        <nav className="px-3 pb-4">
          {drawerItems.map(item => {
            const active = pathname === item.href || pathname.startsWith(item.href + '/')
            return (
              <Link key={item.href} to={item.href} onClick={onClose}
                className={cn(
                  'flex items-center gap-3 px-3 py-3 rounded-xl text-[14px] font-medium',
                  active ? 'text-amber-600 bg-amber-50' : 'text-stone-700 hover:bg-stone-100',
                )}>
                {item.icon}
                {item.label}
              </Link>
            )
          })}
          <div className="my-2 border-t border-stone-100" />
          <button
            onClick={() => { onClose(); nav({ to: '/login' }) }}
            className="flex items-center gap-3 px-3 py-3 rounded-xl text-[14px] font-medium text-stone-600 hover:bg-stone-100 w-full"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            Verrouiller
          </button>
          <button
            onClick={() => { useMassaCorpAuthStore.getState().logout(); massacorpTokenStore.clear(); onClose(); nav({ to: '/login' }) }}
            className="flex items-center gap-3 px-3 py-3 rounded-xl text-[14px] font-medium text-red-600 hover:bg-red-50 w-full"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            Déconnexion
          </button>
        </nav>
      </div>
    </>
  )
}

// ── Bottom nav (téléphone / tablette portrait) ───────────────────────────────

function BottomNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const { canEdit } = useRestaurantScopes()
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Bottom nav adapté au rôle : staff = service-first, manager = pilotage-first
  const bottomHrefs = canEdit ? MANAGER_BOTTOM_HREFS : STAFF_BOTTOM_HREFS
  const allowedItems = visibleItems(NAV_ITEMS, canEdit)
  const allowedExtras = canEdit ? SIDEBAR_EXTRA : []
  const bottomItems = allowedItems.filter(i => bottomHrefs.includes(i.href))
  const drawerItems = [
    ...allowedItems.filter(i => !bottomHrefs.includes(i.href)),
    ...allowedExtras,
  ]
  const drawerActive = drawerItems.some(i => pathname === i.href || pathname.startsWith(i.href + '/'))

  return (
    <>
      <MoreDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} pathname={pathname} drawerItems={drawerItems} />
      <nav className="fixed bottom-0 inset-x-0 bg-white border-t border-stone-200 flex justify-around items-center pb-[env(safe-area-inset-bottom)] z-40 lg:hidden">
        {bottomItems.map(item => (
          <BottomNavItem key={item.href} item={item} pathname={pathname} />
        ))}
        {/* Bouton ··· — masqué si drawer vide */}
        {drawerItems.length > 0 && (
        <button
          onClick={() => setDrawerOpen(v => !v)}
          className={cn('flex flex-col items-center gap-0.5 py-1.5 min-w-[52px] min-h-[44px]', drawerActive ? 'text-amber-600' : 'text-stone-400')}
          aria-label="Plus"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><circle cx="5" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.5" fill="currentColor" stroke="none"/></svg>
          <span className="text-[10px] font-medium">Plus</span>
        </button>
        )}
      </nav>
    </>
  )
}

// ── Layout ────────────────────────────────────────────────────────────────────

export default function RestaurantLayout() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { isAuthenticated } = useMassaCorpAuthStore()
  const [buzzerTrigger, setBuzzerTrigger] = useState(0)
  const [buzzerMessage, setBuzzerMessage] = useState('')

  // Session expirée (REPLAY_DETECTED ou refresh échoué) → redirect login
  useEffect(() => {
    const handler = () => navigate({ to: '/login' })
    window.addEventListener('massacorp:session-expired', handler)
    return () => window.removeEventListener('massacorp:session-expired', handler)
  }, [navigate])

  // Buzzer ticket cuisine en retard (>20 min) — KDS phase 3c
  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<{ table_numero?: number; minutes: number }>
      const tableNum = ce.detail?.table_numero
      const min = ce.detail?.minutes ?? 20
      setBuzzerMessage(tableNum ? `Table ${tableNum} — ${min} min en cuisine !` : `Ticket en retard (${min} min)`)
      setBuzzerTrigger(t => t + 1)
    }
    window.addEventListener('cuisine:ticket-urgent', handler)
    return () => window.removeEventListener('cuisine:ticket-urgent', handler)
  }, [])

  useKdsWebSocket({
    channel: 'salle',
    getToken: () => massacorpTokenStore.getAccessToken(),
    enabled: isAuthenticated,
    onCommandePrete: (data) => {
      const tableNum = (data as { table_numero?: number }).table_numero
      setBuzzerMessage(tableNum ? `Table ${tableNum} — Commande prête !` : 'Commande prête !')
      setBuzzerTrigger(t => t + 1)
      qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
    },
    onLignePrete: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
    },
    onCommandeModifiee: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
    },
  })

  return (
    <div className="flex min-h-screen bg-white text-stone-900">
      <BuzzerAlert trigger={buzzerTrigger} message={buzzerMessage} />

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
