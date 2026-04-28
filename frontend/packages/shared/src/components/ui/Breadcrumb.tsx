import { ReactNode, useRef, useEffect } from 'react';
import { ChevronRight, Home } from 'lucide-react';
import { Link } from '@tanstack/react-router';
import { cn } from '../../lib/utils';

export interface BreadcrumbItem {
  label: string;
  href?: string;
  icon?: ReactNode;
}

export interface BreadcrumbProps {
  items: BreadcrumbItem[];
  showHome?: boolean;
  homeHref?: string;
  separator?: ReactNode;
  className?: string;
}

export function Breadcrumb({
  items,
  showHome = true,
  homeHref = '/dashboard',
  separator,
  className,
}: BreadcrumbProps) {
  const allItems: BreadcrumbItem[] = showHome
    ? [{ label: 'Accueil', href: homeHref, icon: <Home className="w-4 h-4" /> }, ...items]
    : items;

  return (
    <nav aria-label="Fil d'Ariane" className={className}>
      <ol className="flex items-center flex-wrap gap-1 text-sm">
        {allItems.map((item, index) => {
          const isLast = index === allItems.length - 1;

          return (
            <li key={index} className="flex items-center">
              {index > 0 && (
                <span className="mx-2 text-dark-500">
                  {separator || <ChevronRight className="w-4 h-4" />}
                </span>
              )}
              {isLast ? (
                <span className="flex items-center gap-1.5 text-dark-300 font-medium">
                  {item.icon}
                  {item.label}
                </span>
              ) : item.href ? (
                <Link
                  to={item.href}
                  className={cn(
                    'flex items-center gap-1.5 text-dark-400 hover:text-dark-100 transition-colors',
                    index === 0 && 'text-dark-500'
                  )}
                >
                  {item.icon}
                  {index > 0 && item.label}
                </Link>
              ) : (
                <span className="flex items-center gap-1.5 text-dark-400">
                  {item.icon}
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

// 20 threshold steps for IntersectionObserver interpolation
const IO_THRESHOLDS = Array.from({ length: 21 }, (_, i) => i / 20)

// Page Header avec Breadcrumb intégré + iOS-style crossfade
export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: ReactNode;
  className?: string;
  /** Callback when title changes (for inline header title) */
  onTitleChange?: (title: string) => void;
  /** Callback with scroll progress 0→1 (for crossfade interpolation) */
  onProgressChange?: (progress: number) => void;
}

export function PageHeader({
  title,
  subtitle,
  breadcrumbs,
  actions,
  className,
  onTitleChange,
  onProgressChange,
}: PageHeaderProps) {
  const titleRef = useRef<HTMLHeadingElement>(null)

  // Push title to context
  useEffect(() => {
    onTitleChange?.(title)
  }, [title, onTitleChange])

  // IntersectionObserver for crossfade progress
  useEffect(() => {
    const el = titleRef.current
    if (!el || !onProgressChange) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        // ratio: 1 = fully visible, 0 = fully out
        onProgressChange(1 - entry.intersectionRatio)
      },
      {
        threshold: IO_THRESHOLDS,
        rootMargin: '-56px 0px 0px 0px', // offset by header height
      },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [onProgressChange])

  return (
    <div className={cn('mb-6', className)}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumb items={breadcrumbs} className="mb-4" />
      )}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 ref={titleRef} className="text-2xl font-bold tracking-tight">{title}</h1>
          {subtitle && (
            <p className="mt-1 text-[var(--muted)] text-sm">{subtitle}</p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  );
}
