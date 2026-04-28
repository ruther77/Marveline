import { useState, useEffect, useRef, useCallback } from 'react'
import { Outlet, Link, useNavigate, useRouterState } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/authStore'
import { useLogout } from '@/api/queries/useAuth'
import { cn } from '@/lib/utils'
import { PageErrorBoundary } from '@/components/errors'
import OfflineBanner from '@/components/errors/OfflineBanner'
import NotificationBell from '@/layout/NotificationBell'
import GlobalSearch from '@/layout/GlobalSearch'
import { HeaderTitleProvider, useHeaderTitle } from '@/layout/HeaderTitleContext'
import { useScrollVelocity } from '@shared/hooks/useScrollVelocity'
import {
  LayoutDashboard,
  CalendarDays,
  CalendarCheck,
  ScanLine,
  MoreHorizontal,
  LogOut,
  ChevronDown,
  User,
  Lock,
  Smartphone,
  Monitor,
  Sun,
  Moon,
  Shield,
} from 'lucide-react'
import { useTheme, type Theme } from '@/stores/uiStore'
import { useBrand } from '@/brand/select'

// ── Velocity-aware scroll hide ──────────────────────────────────────────────

function useScrollHideVelocity() {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const headerRef = useRef<HTMLElement>(null)
  const bottomNavRef = useRef<HTMLElement>(null)
  const progressRef = useRef(0) // 0 = visible, 1 = hidden
  const isTransitioning = useRef(false)

  const applyProgress = useCallback((p: number) => {
    const clamped = Math.max(0, Math.min(1, p))
    progressRef.current = clamped

    // Apply CSS custom property for downstream consumers (SubNav, backdrop)
    const wrapper = wrapperRef.current
    if (wrapper) {
      wrapper.style.setProperty('--hide-progress', String(clamped))
    }

    // Header transform + backdrop blur (JS-driven, no CSS transition)
    const header = headerRef.current
    if (header && !isTransitioning.current) {
      header.style.transform = `translateY(${-clamped * 100}%)`
      // Backdrop blur: full when visible + scrolled, none when hidden
      const blur = 20 * (1 - clamped)
      const saturate = 100 + 80 * (1 - clamped)
      const bgOpacity = 0.85 * (1 - clamped * 0.5)
      header.style.backdropFilter = `blur(${blur}px) saturate(${saturate}%)`
      ;(header.style as unknown as Record<string, string>).WebkitBackdropFilter = `blur(${blur}px) saturate(${saturate}%)`
      header.style.backgroundColor = `color-mix(in srgb, var(--s1) ${Math.round(bgOpacity * 100)}%, transparent)`
    }

    // Bottom nav transform
    const bottomNav = bottomNavRef.current
    if (bottomNav && !isTransitioning.current) {
      bottomNav.style.transform = `translateY(${clamped * 100}%)`
    }
  }, [])

  // Smooth transition for tap-reveal
  const transitionTo = useCallback((target: number) => {
    isTransitioning.current = true
    const header = headerRef.current
    const bottomNav = bottomNavRef.current

    const dur = '250ms'
    const ease = 'cubic-bezier(0.25, 0.46, 0.45, 0.94)'
    if (header) header.style.transition = `transform ${dur} ${ease}, backdrop-filter ${dur} ${ease}`
    if (bottomNav) bottomNav.style.transition = `transform ${dur} ${ease}`

    requestAnimationFrame(() => {
      applyProgress(target)
      setTimeout(() => {
        isTransitioning.current = false
        if (header) header.style.transition = 'none'
        if (bottomNav) bottomNav.style.transition = 'none'
      }, 260)
    })
  }, [applyProgress])

  useScrollVelocity(useCallback(({ scrollY, velocity }) => {
    if (isTransitioning.current) return

    // Always visible at top
    if (scrollY <= 5) {
      if (progressRef.current > 0) applyProgress(0)
      return
    }

    // Ignore overscroll bounce
    if (scrollY < 0) return

    const current = progressRef.current

    // Fast scroll down (velocity > 12) → hide immediately
    if (velocity > 12 && current < 1) {
      applyProgress(1)
      return
    }

    // Fast scroll up (velocity < -5) → show immediately
    if (velocity < -5 && current > 0) {
      applyProgress(0)
      return
    }

    // Slow scroll → interpolate progressively
    if (velocity > 1 && current < 1) {
      applyProgress(Math.min(1, current + velocity * 0.02))
    } else if (velocity < -1 && current > 0) {
      applyProgress(Math.max(0, current + velocity * 0.02))
    }
  }, [applyProgress]))

  // Tap to reveal (touchend without movement)
  useEffect(() => {
    let touchStartY = 0
    let didMove = false

    const onTouchStart = (e: TouchEvent) => {
      touchStartY = e.touches[0].clientY
      didMove = false
    }
    const onTouchMove = (e: TouchEvent) => {
      if (Math.abs(e.touches[0].clientY - touchStartY) > 5) didMove = true
    }
    const onTouchEnd = () => {
      if (!didMove && progressRef.current > 0.5) {
        transitionTo(0)
      }
    }

    document.addEventListener('touchstart', onTouchStart, { passive: true })
    document.addEventListener('touchmove', onTouchMove, { passive: true })
    document.addEventListener('touchend', onTouchEnd, { passive: true })
    return () => {
      document.removeEventListener('touchstart', onTouchStart)
      document.removeEventListener('touchmove', onTouchMove)
      document.removeEventListener('touchend', onTouchEnd)
    }
  }, [transitionTo])

  return { wrapperRef, headerRef, bottomNavRef, transitionTo }
}

// ── Spring scroll to top ────────────────────────────────────────────────────

function springScrollToTop() {
  const start = window.scrollY
  if (start <= 0) return
  const duration = Math.min(600, start * 0.4)
  const startTime = performance.now()

  function animate(time: number) {
    const t = Math.min((time - startTime) / duration, 1)
    const eased = 1 - Math.pow(1 - t, 4) // ease-out quart (spring feel)
    window.scrollTo(0, start * (1 - eased))
    if (t < 1) requestAnimationFrame(animate)
  }
  requestAnimationFrame(animate)
}

// ── Bottom nav definition ───────────────────────────────────────────────────

interface BottomNavEntry {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  prefixes: string[]
}

const BOTTOM_NAV: BottomNavEntry[] = [
  {
    name: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
    prefixes: ['/dashboard', '/notifications'],
  },
  {
    name: 'Planning',
    href: '/planning/calendar',
    icon: CalendarDays,
    prefixes: ['/planning'],
  },
  {
    name: 'Réservations',
    href: '/reservations',
    icon: CalendarCheck,
    prefixes: ['/reservations'],
  },
  {
    name: 'Opérations',
    href: '/operations',
    icon: ScanLine,
    prefixes: ['/operations'],
  },
  {
    name: 'Plus',
    href: '/plus',
    icon: MoreHorizontal,
    prefixes: [
      '/plus',
      '/customers',
      '/stock',
      '/catalogue',
      '/finance',
      '/devis',
      '/profile',
      '/admin',
      '/evenements',
    ],
  },
]

const profileNavigation = [
  { name: 'Mon Profil', href: '/profile', icon: User },
  { name: 'Sécurité', href: '/profile/security', icon: Lock },
  { name: '2FA', href: '/profile/mfa', icon: Smartphone },
]

// ── Inline title component ──────────────────────────────────────────────────

function InlineTitle() {
  const { state } = useHeaderTitle()
  if (!state.title) return null

  return (
    <span
      className="text-sm font-semibold truncate max-w-[160px] transition-opacity duration-150"
      style={{ opacity: state.progress }}
    >
      {state.title}
    </span>
  )
}

// ── Main component ──────────────────────────────────────────────────────────

function DashboardLayoutInner() {
  const brand = useBrand()
  const [profileOpen, setProfileOpen] = useState(false)
  const { user, logout } = useAuthStore()
  const logoutMutation = useLogout()
  const { theme, setTheme } = useTheme()
  const navigate = useNavigate()
  const routerState = useRouterState()
  const pathname = routerState.location.pathname
  const { wrapperRef, headerRef, bottomNavRef } = useScrollHideVelocity()

  useEffect(() => {
    const handler = () => navigate({ to: '/login' })
    window.addEventListener('auth:session-expired', handler)
    return () => window.removeEventListener('auth:session-expired', handler)
  }, [navigate])

  const handleLogout = async () => {
    try {
      await logoutMutation.mutateAsync()
    } finally {
      logout()
      navigate({ to: '/login' })
    }
  }

  const isEntryActive = (entry: BottomNavEntry) =>
    entry.prefixes.some((p) => pathname === p || pathname.startsWith(p + '/'))

  const handleHeaderClick = (e: React.MouseEvent) => {
    // Don't trigger scroll-to-top if clicking a button/link inside the header
    const target = e.target as HTMLElement
    if (target.closest('button, a, input')) return
    springScrollToTop()
  }

  return (
    <div
      ref={wrapperRef}
      className="min-h-screen bg-bg pb-[calc(64px+env(safe-area-inset-bottom,0px))] lg:pb-0"
      style={{ '--hide-progress': '0' } as React.CSSProperties}
    >

      {/* Header */}
      <header
        ref={headerRef}
        className="fixed top-0 left-0 right-0 z-30 border-b border-[var(--border)] safe-area-pt will-change-transform lg:sticky lg:top-0"
        style={{
          transform: 'translateY(0)',
          backdropFilter: 'blur(20px) saturate(180%)',
          WebkitBackdropFilter: 'blur(20px) saturate(180%)',
          backgroundColor: 'color-mix(in srgb, var(--s1) 85%, transparent)',
        }}
        onClick={handleHeaderClick}
      >
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 lg:px-6 h-14">
          {/* Logo */}
          <Link to="/dashboard" className="flex items-center gap-2.5 shrink-0">
            <div
              className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center"
              style={{ boxShadow: `0 4px 12px rgb(${brand.colors.primaryRgb} / 0.3)` }}
            >
              <Shield className="w-5 h-5 text-white" />
            </div>
            <span className="text-base font-bold hidden sm:block">{brand.shortName}</span>
          </Link>

          {/* Inline title — fades in when large title scrolls out */}
          <div className="flex-1 flex items-center justify-center px-4 lg:hidden">
            <InlineTitle />
          </div>

          <div className="flex items-center gap-1">
            <GlobalSearch />
            <NotificationBell />

            {/* User menu */}
            <div className="relative">
              <button
                data-testid="user-menu"
                onClick={() => setProfileOpen(!profileOpen)}
                className="flex items-center gap-2 px-2 py-2 rounded-xl hover:bg-[var(--s2)] transition-colors min-h-[44px]"
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-sm font-semibold text-white">
                  {user?.first_name?.[0]}{user?.last_name?.[0]}
                </div>
                <ChevronDown className="w-3.5 h-3.5 text-dark-400 hidden sm:block" />
              </button>

              {profileOpen && (
                <>
                  <div className="fixed inset-0 z-40" aria-hidden="true" onClick={() => setProfileOpen(false)} />
                  <div
                    className="absolute right-0 mt-2 w-56 bg-[var(--s1)] border border-[var(--border2)] rounded-xl z-50 overflow-hidden shadow-xl"
                    style={{ boxShadow: 'var(--shadow-xl)' }}
                  >
                    <div className="p-2">
                      <div className="px-4 py-2 mb-1">
                        <p className="text-sm font-medium">{user?.first_name} {user?.last_name}</p>
                        <p className="text-xs text-dark-400 truncate">{user?.email}</p>
                      </div>
                      <hr className="my-1 border-[var(--border)]" />
                      {profileNavigation.map((item) => (
                        <Link
                          key={item.href}
                          to={item.href}
                          className="flex items-center gap-4 px-4 py-2.5 rounded-lg text-sm text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--s2)] transition-colors min-h-[44px]"
                          onClick={() => setProfileOpen(false)}
                        >
                          <item.icon className="w-4 h-4" />
                          {item.name}
                        </Link>
                      ))}
                      <hr className="my-1 border-[var(--border)]" />
                      <div className="px-4 py-1.5">
                        <p className="text-[11px] font-medium text-dark-400 uppercase tracking-wide mb-1.5">Apparence</p>
                        <div className="flex gap-1">
                          {([
                            { value: 'light', icon: Sun, label: 'Clair' },
                            { value: 'dark', icon: Moon, label: 'Sombre' },
                            { value: 'system', icon: Monitor, label: 'Système' },
                          ] as { value: Theme; icon: React.ComponentType<{ className?: string }>; label: string }[]).map(({ value, icon: Icon, label }) => (
                            <button
                              key={value}
                              onClick={() => setTheme(value)}
                              title={label}
                              className={cn(
                                'flex-1 flex flex-col items-center gap-1 py-2 rounded-lg text-[11px] font-medium transition-colors',
                                theme === value
                                  ? 'bg-primary-500/15 text-primary-400'
                                  : 'text-dark-400 hover:bg-[var(--s2)] hover:text-dark-100'
                              )}
                            >
                              <Icon className="w-4 h-4" />
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <hr className="my-1 border-[var(--border)]" />
                      <button
                        onClick={handleLogout}
                        disabled={logoutMutation.isPending}
                        className="flex items-center gap-4 w-full px-4 py-2.5 rounded-lg text-sm text-danger hover:bg-danger/10 transition-colors min-h-[44px]"
                      >
                        <LogOut className="w-4 h-4" />
                        Déconnexion
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Desktop tabs — lg+ only */}
        <nav className="hidden lg:flex items-center gap-1 px-6 border-t border-[var(--border)]/50 overflow-x-auto scrollbar-none">
          {BOTTOM_NAV.map((entry) => {
            const active = isEntryActive(entry)
            return (
              <Link
                key={entry.href}
                to={entry.href}
                className={cn(
                  'flex items-center gap-2 px-4 py-4 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px',
                  active
                    ? 'border-primary-500 text-primary-400'
                    : 'border-transparent text-dark-400 hover:text-dark-100 hover:border-[var(--border)]'
                )}
              >
                <entry.icon className="w-4 h-4" />
                {entry.name}
              </Link>
            )
          })}
        </nav>
      </header>

      {/* Spacer for fixed header on mobile */}
      <div className="h-14 safe-area-pt lg:hidden" />

      <OfflineBanner />

      {/* Main content */}
      <main className="p-4 lg:p-6">
        <PageErrorBoundary>
          <Outlet />
        </PageErrorBoundary>
      </main>

      {/* Bottom Navigation */}
      <nav
        ref={bottomNavRef}
        className="fixed bottom-0 left-0 right-0 z-40 lg:hidden border-t border-[var(--border)] safe-area-pb will-change-transform"
        style={{
          transform: 'translateY(0)',
          backdropFilter: 'blur(20px) saturate(180%)',
          WebkitBackdropFilter: 'blur(20px) saturate(180%)',
          backgroundColor: 'color-mix(in srgb, var(--s1) 85%, transparent)',
        }}
      >
        <div className="flex items-stretch justify-around px-1 h-16">
          {BOTTOM_NAV.map((entry) => {
            const active = isEntryActive(entry)
            return (
              <Link
                key={entry.href}
                to={entry.href}
                className={cn(
                  'relative flex flex-col items-center justify-center gap-0.5 flex-1 text-[11px] font-medium min-h-[44px]',
                  'transition-all duration-150 active:scale-90 active:opacity-70',
                  active ? 'text-primary-400' : 'text-dark-400'
                )}
              >
                <entry.icon className={cn(
                  'w-5 h-5 transition-transform duration-200',
                  active && 'scale-110'
                )} />
                <span>{entry.name}</span>
                {active && (
                  <span className="absolute bottom-1 left-1/2 -translate-x-1/2 w-5 h-[3px] rounded-full bg-primary-500" />
                )}
              </Link>
            )
          })}
        </div>
      </nav>
    </div>
  )
}

// ── Export with provider ─────────────────────────────────────────────────────

export default function DashboardLayout() {
  return (
    <HeaderTitleProvider>
      <DashboardLayoutInner />
    </HeaderTitleProvider>
  )
}
