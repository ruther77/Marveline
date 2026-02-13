import { useState, useCallback } from 'react'
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'
import { cn } from '@/lib/utils'
import { useResponsive } from '@/hooks/useMediaQuery'
import {
  LayoutDashboard,
  ShoppingCart,
  BarChart3,
  Wallet,
  Settings,
  LogOut,
  Menu,
  X,
  ChevronDown,
  ChevronRight,
  Users,
  Monitor,
  FileText,
  User,
  Lock,
  Smartphone,
  Shield,
  Calendar,
  Package,
  TrendingUp,
} from 'lucide-react'

// --- Types ---

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string | number
}

interface NavGroup {
  name: string
  href?: string
  icon: React.ComponentType<{ className?: string }>
  children?: NavItem[]
}

// --- Navigation data ---

const navigation: NavGroup[] = [
  { name: 'Accueil', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Agenda', href: '/agenda', icon: Calendar },
  {
    name: 'Catalogue', icon: Package,
    children: [
      { name: 'Produits', href: '/products', icon: Package },
      { name: 'Catégories', href: '/products/categories', icon: Package },
      { name: 'Formules', href: '/products/bundles', icon: Package },
    ],
  },
  {
    name: 'Ventes', icon: ShoppingCart,
    children: [
      { name: 'Événements', href: '/events', icon: Calendar },
    ],
  },
  {
    name: 'Stock', icon: TrendingUp,
    children: [
      { name: 'Inventaire', href: '/inventory/stock', icon: Package },
      { name: 'Arrivées/Retours', href: '/inventory/movements', icon: TrendingUp },
    ],
  },
  {
    name: 'Gestion', icon: Settings,
    children: [
      { name: 'Utilisateurs', href: '/admin/users', icon: Users },
      { name: 'Sessions', href: '/admin/sessions', icon: Monitor },
    ],
  },
  { name: 'Finances', href: '/finances', icon: Wallet },
  {
    name: 'Rapports', icon: BarChart3,
    children: [
      { name: 'Audit Logs', href: '/admin/audit-logs', icon: FileText },
    ],
  },
]

const profileNavigation: NavItem[] = [
  { name: 'Mon Profil', href: '/profile', icon: User },
  { name: 'Securite', href: '/profile/security', icon: Lock },
  { name: '2FA', href: '/profile/mfa', icon: Smartphone },
]

// --- Component ---

export default function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [openMenus, setOpenMenus] = useState<Set<string>>(new Set())
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const { isMobile, isTablet, isDesktop } = useResponsive()

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } finally {
      logout()
      navigate('/login')
    }
  }

  const isActiveSection = (href: string) => {
    if (href === '/dashboard') return location.pathname === '/dashboard'
    return location.pathname.startsWith(href)
  }

  const isGroupActive = (group: NavGroup) => {
    if (group.href) return isActiveSection(group.href)
    return group.children?.some((child) => isActiveSection(child.href)) ?? false
  }

  const toggleMenu = useCallback((name: string) => {
    setOpenMenus((prev) => {
      const next = new Set(prev)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })
  }, [])

  // --- Sidebar nav item (leaf) ---
  const SidebarNavItem = ({ item, isChild = false }: { item: NavItem; isChild?: boolean }) => (
    <NavLink
      to={item.href}
      className={() =>
        cn(
          'flex items-center gap-3 rounded-xl text-sm font-medium transition-all duration-200 min-h-[44px]',
          isChild ? 'pl-11 pr-3 py-2 text-[13px]' : 'px-3 py-2.5 text-[15px]',
          isActiveSection(item.href)
            ? 'bg-primary-600 text-white shadow-lg shadow-primary-600/25'
            : 'text-dark-400 hover:text-white hover:bg-dark-700/50'
        )
      }
      onClick={() => setSidebarOpen(false)}
    >
      {isChild && (
        <span className={cn(
          'w-1.5 h-1.5 rounded-full flex-shrink-0',
          isActiveSection(item.href) ? 'bg-white' : 'bg-primary-400'
        )} />
      )}
      {!isChild && <item.icon className="w-5 h-5 flex-shrink-0" />}
      {(isDesktop || sidebarOpen || !isTablet) && <span>{item.name}</span>}
      {item.badge && (
        <span className="ml-auto px-2 py-0.5 text-xs bg-primary-500/20 text-primary-400 rounded-full">
          {item.badge}
        </span>
      )}
    </NavLink>
  )

  // --- Sidebar nav group (accordion parent) ---
  const SidebarNavGroup = ({ group }: { group: NavGroup }) => {
    const hasChildren = group.children && group.children.length > 0
    const isOpen = openMenus.has(group.name)
    const active = isGroupActive(group)

    // Direct link (no children)
    if (!hasChildren && group.href) {
      return (
        <SidebarNavItem
          item={{ name: group.name, href: group.href, icon: group.icon }}
        />
      )
    }

    // Empty group (no children, no href) — just a placeholder
    if (!hasChildren && !group.href) {
      return (
        <button
          className={cn(
            'flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-[15px] font-medium transition-all duration-200 min-h-[44px]',
            'text-dark-500 cursor-default'
          )}
          disabled
        >
          <group.icon className="w-5 h-5 flex-shrink-0" />
          {(isDesktop || sidebarOpen || !isTablet) && (
            <>
              <span>{group.name}</span>
              <span className="ml-auto text-[11px] text-dark-600">Bientot</span>
            </>
          )}
        </button>
      )
    }

    // Accordion group
    return (
      <div>
        <button
          onClick={() => toggleMenu(group.name)}
          className={cn(
            'flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-[15px] font-medium transition-all duration-200 min-h-[44px]',
            active
              ? 'text-white bg-dark-700/50'
              : 'text-dark-400 hover:text-white hover:bg-dark-700/50'
          )}
        >
          <group.icon className="w-5 h-5 flex-shrink-0" />
          {(isDesktop || sidebarOpen || !isTablet) && (
            <>
              <span className="flex-1 text-left">{group.name}</span>
              <ChevronRight
                className={cn(
                  'w-4 h-4 text-dark-500 transition-transform duration-200',
                  isOpen && 'rotate-90'
                )}
              />
            </>
          )}
        </button>

        {/* Accordion children */}
        <div
          className={cn(
            'accordion-enter',
            isOpen && 'accordion-open'
          )}
        >
          <div className="mt-1 space-y-0.5">
            {group.children!.map((child) => (
              <SidebarNavItem key={child.href} item={child} isChild />
            ))}
          </div>
        </div>
      </div>
    )
  }

  // --- Bottom nav item (mobile) ---
  const BottomNavItem = ({ group }: { group: NavGroup }) => {
    const active = isGroupActive(group)
    const href = group.href || group.children?.[0]?.href || '#'

    const handleClick = () => {
      if (group.children && group.children.length > 0 && !group.href) {
        // Open sidebar for groups with children
        setSidebarOpen(true)
        // Auto-open this group's accordion
        setOpenMenus((prev) => new Set(prev).add(group.name))
        return
      }
    }

    if (group.href) {
      return (
        <NavLink
          to={group.href}
          className={() =>
            cn(
              'flex flex-col items-center gap-1 px-2 py-2 rounded-lg text-[11px] font-medium transition-all duration-200 min-w-[56px] min-h-[44px] justify-center',
              active ? 'text-primary-400' : 'text-dark-500 hover:text-dark-300'
            )
          }
        >
          <group.icon className={cn('w-5 h-5 transition-all duration-200', active && 'scale-110')} />
          <span>{group.name}</span>
          {active && <span className="w-1 h-1 rounded-full bg-primary-400 -mt-0.5" />}
        </NavLink>
      )
    }

    return (
      <button
        onClick={handleClick}
        className={cn(
          'flex flex-col items-center gap-1 px-2 py-2 rounded-lg text-[11px] font-medium transition-all duration-200 min-w-[56px] min-h-[44px] justify-center',
          active ? 'text-primary-400' : 'text-dark-500 hover:text-dark-300'
        )}
      >
        <group.icon className={cn('w-5 h-5 transition-all duration-200', active && 'scale-110')} />
        <span>{group.name}</span>
        {active && <span className="w-1 h-1 rounded-full bg-primary-400 -mt-0.5" />}
      </button>
    )
  }

  return (
    <div className="min-h-screen bg-dark-900 pb-20 lg:pb-0">
      {/* Mobile/Tablet sidebar backdrop */}
      {sidebarOpen && !isDesktop && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed top-0 left-0 z-50 h-full bg-dark-800/95 backdrop-blur-xl border-r border-dark-700/50 transform transition-transform duration-200',
          // Width: collapsed on tablet, expanded on desktop/mobile-open
          isTablet && !sidebarOpen ? 'w-[68px]' : 'w-72',
          // Visibility
          isDesktop
            ? 'translate-x-0'
            : isTablet
              ? 'translate-x-0'
              : sidebarOpen
                ? 'translate-x-0'
                : '-translate-x-full'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between p-5 border-b border-dark-700/50 safe-area-pt">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-lg shadow-primary-500/25 flex-shrink-0">
                <Shield className="w-6 h-6 text-white" />
              </div>
              {(isDesktop || sidebarOpen || !isTablet) && (
                <div>
                  <span className="text-lg font-bold text-white">Marveline</span>
                  <p className="text-xs text-dark-500">Gestion unifiee</p>
                </div>
              )}
            </div>
            {!isDesktop && sidebarOpen && (
              <button
                className="text-dark-400 hover:text-white p-1 min-h-[44px] min-w-[44px] flex items-center justify-center"
                onClick={() => setSidebarOpen(false)}
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto scrollbar-thin">
            {navigation.map((group) => (
              <SidebarNavGroup key={group.name} group={group} />
            ))}
          </nav>

          {/* User section */}
          <div className="p-4 border-t border-dark-700/50">
            {(isDesktop || sidebarOpen || !isTablet) ? (
              <>
                <div className="flex items-center gap-3 px-3 py-2 rounded-xl bg-dark-700/30">
                  <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-sm font-medium text-white flex-shrink-0">
                    {user?.first_name?.[0]}{user?.last_name?.[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">
                      {user?.first_name} {user?.last_name}
                    </p>
                    <p className="text-xs text-dark-500 truncate">{user?.email}</p>
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-3 w-full mt-2 px-3 py-2.5 rounded-xl text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors min-h-[44px]"
                >
                  <LogOut className="w-5 h-5" />
                  Deconnexion
                </button>
              </>
            ) : (
              /* Tablet collapsed: avatar only */
              <div className="flex flex-col items-center gap-2">
                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-sm font-medium text-white">
                  {user?.first_name?.[0]}{user?.last_name?.[0]}
                </div>
                <button
                  onClick={handleLogout}
                  className="text-red-400 hover:text-red-300 p-2 rounded-lg hover:bg-red-500/10 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                  title="Deconnexion"
                >
                  <LogOut className="w-5 h-5" />
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className={cn(
        'transition-all duration-200',
        isDesktop ? 'pl-72' : isTablet ? 'pl-[68px]' : 'pl-0'
      )}>
        {/* Header */}
        <header className="sticky top-0 z-30 bg-dark-900/80 backdrop-blur-xl border-b border-dark-700/50 safe-area-pt">
          <div className="flex items-center justify-between px-4 lg:px-6 h-14">
            {/* Left: hamburger (mobile) or logo small (tablet) */}
            {isMobile && (
              <button
                className="text-dark-400 hover:text-white p-2 -ml-2 min-h-[44px] min-w-[44px] flex items-center justify-center"
                onClick={() => setSidebarOpen(true)}
              >
                <Menu className="w-6 h-6" />
              </button>
            )}

            {/* Mobile: centered logo */}
            {isMobile && (
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-primary-500" />
                <span className="text-sm font-bold text-white">Marveline</span>
              </div>
            )}

            <div className="flex-1" />

            {/* User dropdown - Desktop/Tablet */}
            {(isDesktop || isTablet) && (
              <div className="relative">
                <button
                  onClick={() => setProfileOpen(!profileOpen)}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl hover:bg-dark-700/50 transition-colors min-h-[44px]"
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-sm font-medium text-white">
                    {user?.first_name?.[0]}{user?.last_name?.[0]}
                  </div>
                  <ChevronDown className="w-4 h-4 text-dark-400" />
                </button>

                {profileOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setProfileOpen(false)}
                    />
                    <div className="absolute right-0 mt-2 w-56 bg-dark-800 border border-dark-700 rounded-xl shadow-xl z-50 overflow-hidden">
                      <div className="p-2">
                        {profileNavigation.map((item) => (
                          <NavLink
                            key={item.href}
                            to={item.href}
                            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-dark-300 hover:text-white hover:bg-dark-700/50 transition-colors min-h-[44px]"
                            onClick={() => setProfileOpen(false)}
                          >
                            <item.icon className="w-4 h-4" />
                            {item.name}
                          </NavLink>
                        ))}
                        <hr className="my-2 border-dark-700" />
                        <button
                          onClick={handleLogout}
                          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors min-h-[44px]"
                        >
                          <LogOut className="w-4 h-4" />
                          Deconnexion
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Mobile: avatar only (profile via sidebar) */}
            {isMobile && (
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-sm font-medium text-white">
                {user?.first_name?.[0]}{user?.last_name?.[0]}
              </div>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-6">
          <Outlet />
        </main>
      </div>

      {/* Bottom Navigation - Mobile only */}
      {isMobile && (
        <nav className="fixed bottom-0 left-0 right-0 z-40 bg-dark-800/95 backdrop-blur-xl border-t border-dark-700/50 safe-area-pb">
          <div className="flex items-center justify-around px-2 py-1">
            {navigation.map((group) => (
              <BottomNavItem key={group.name} group={group} />
            ))}
          </div>
        </nav>
      )}
    </div>
  )
}
