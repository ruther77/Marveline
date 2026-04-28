import { ReactNode, useRef, useEffect } from 'react';
import { Link, useRouterState } from '@tanstack/react-router';
import { cn } from '@/lib/utils';

export interface SubNavItem {
  label: string;
  href: string;
  icon?: ReactNode;
  badge?: string | number;
}

export interface SubNavProps {
  items: SubNavItem[];
  className?: string;
}

/**
 * Reads --hide-progress CSS var from the layout wrapper.
 * Uses RAF polling instead of MutationObserver for smooth sync.
 */
function useHideProgress(navRef: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = navRef.current
    if (!el) return

    let rafId = 0
    function tick() {
      const wrapper = el!.closest('[style*="--hide-progress"]') as HTMLElement | null
      if (wrapper) {
        const progress = parseFloat(wrapper.style.getPropertyValue('--hide-progress') || '0')
        el!.style.transform = `translateY(${-progress * 100}%)`
        el!.style.opacity = String(1 - progress)
        el!.style.pointerEvents = progress > 0.5 ? 'none' : 'auto'
      }
      rafId = requestAnimationFrame(tick)
    }
    rafId = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafId)
  }, [navRef])
}

export function SubNav({ items, className }: SubNavProps) {
  const routerState = useRouterState()
  const pathname = routerState.location.pathname
  const navRef = useRef<HTMLElement>(null)
  useHideProgress(navRef)

  return (
    <nav
      ref={navRef}
      className={cn(
        'sticky top-14 z-20 flex items-center gap-2 px-4 py-2.5',
        'border-b border-[var(--border)]/50 will-change-transform',
        'flex-wrap lg:flex-nowrap lg:overflow-x-auto lg:scrollbar-none',
        'lg:translate-y-0 lg:opacity-100 lg:pointer-events-auto',
        className
      )}
      style={{
        backgroundColor: 'color-mix(in srgb, var(--bg) 85%, transparent)',
        backdropFilter: 'blur(16px) saturate(180%)',
        WebkitBackdropFilter: 'blur(16px) saturate(180%)',
      }}
    >
      {items.map((item) => {
        const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
        return (
          <Link
            key={item.href}
            to={item.href}
            className={cn(
              'flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap border',
              'transition-all duration-150 active:scale-95 active:opacity-80',
              isActive
                ? 'bg-primary-500 border-primary-500 text-white'
                : 'bg-[var(--s1)] border-[var(--border2)] text-[var(--muted)] hover:text-[var(--text)]'
            )}
          >
            {item.icon && <span className="w-4 h-4">{item.icon}</span>}
            <span>{item.label}</span>
            {item.badge !== undefined && (
              <span className={cn(
                'ml-1 px-1.5 py-0.5 text-xs rounded-full',
                isActive ? 'bg-white/20 text-white' : 'bg-[var(--s2)] text-[var(--muted)]'
              )}>
                {item.badge}
              </span>
            )}
          </Link>
        )
      })}
    </nav>
  );
}

// Version avec tabs (non-routée)
export interface TabItem {
  id: string;
  label: string;
  icon?: ReactNode;
  badge?: string | number;
}

export interface TabNavProps {
  tabs: TabItem[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  className?: string;
}

export function TabNav({ tabs, activeTab, onTabChange, className }: TabNavProps) {
  return (
    <nav
      className={cn(
        'flex items-center gap-2 px-4 py-2',
        'flex-wrap lg:flex-nowrap lg:overflow-x-auto lg:scrollbar-none',
        className
      )}
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            'flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap border',
            'transition-all duration-150 active:scale-95 active:opacity-80',
            activeTab === tab.id
              ? 'bg-primary-500 border-primary-500 text-white'
              : 'bg-[var(--s1)] border-[var(--border2)] text-[var(--muted)] hover:text-[var(--text)]'
          )}
        >
          {tab.icon && <span className="w-4 h-4">{tab.icon}</span>}
          <span>{tab.label}</span>
          {tab.badge !== undefined && (
            <span className={cn(
              'ml-1 px-1.5 py-0.5 text-xs rounded-full',
              activeTab === tab.id ? 'bg-white/20 text-white' : 'bg-[var(--s2)] text-[var(--muted)]'
            )}>
              {tab.badge}
            </span>
          )}
        </button>
      ))}
    </nav>
  );
}
