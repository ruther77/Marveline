/**
 * Skeleton patterns structurés — LOW fidelity (animate-pulse)
 * Chaque skeleton reproduit fidèlement la structure de la page finale.
 *
 * Usage: import { PageDetailSkeleton } from '@shared/components/ui/SkeletonPatterns'
 */

import { cn } from '../../lib/utils'

// ── Primitives ────────────────────────────────────────────────────────────────

function Bone({ className }: { className: string }) {
  return <div className={cn('bg-dark-800 rounded', className)} />
}

function BonePill({ className }: { className?: string }) {
  return <div className={cn('bg-dark-800 rounded-full h-5 w-16', className)} />
}

function BoneCircle({ size = 'w-10 h-10' }: { size?: string }) {
  return <div className={cn('bg-dark-800 rounded-full shrink-0', size)} />
}

// ── Image placeholder (MID state — structure visible, image loading) ──────────

export function ImagePlaceholder({ className }: { className?: string }) {
  return (
    <div className={cn('bg-dark-800 rounded-lg flex items-center justify-center', className)}>
      <svg className="w-8 h-8 text-dark-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
      </svg>
    </div>
  )
}

// ── Page Skeleton: Reservation Phase ──────────────────────────────────────────
// Hero + Alert + InfoGrid(4) + ProductLines + Actions + QuickLinks

export function ReservationPhaseSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      {/* Hero */}
      <div className="rounded-xl border border-dark-700 p-4 space-y-3">
        {/* breadcrumb */}
        <Bone className="h-3 w-32" />
        {/* reference + status badge */}
        <div className="flex items-center justify-between">
          <Bone className="h-6 w-40" />
          <BonePill />
        </div>
        {/* client + montant */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BoneCircle size="w-6 h-6" />
            <Bone className="h-4 w-28" />
          </div>
          <Bone className="h-5 w-20" />
        </div>
        {/* progress bar */}
        <Bone className="h-2 w-full rounded-full" />
      </div>

      {/* Status alert */}
      <Bone className="h-12 w-full rounded-lg" />

      {/* Info grid 2x2 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="bg-dark-900/60 rounded-lg p-4 space-y-2">
            <Bone className="h-3 w-16" />
            <Bone className="h-4 w-20" />
          </div>
        ))}
      </div>

      {/* Product lines */}
      <div className="border-t border-dark-700 pt-4 space-y-3">
        <div className="flex items-center justify-between">
          <Bone className="h-4 w-28" />
          <Bone className="h-4 w-16" />
        </div>
        {[1, 2, 3].map(i => (
          <div key={i} className="flex items-center gap-3 py-2">
            <div className="w-10 h-10 bg-dark-800 rounded-lg shrink-0" />
            <div className="flex-1 space-y-1">
              <Bone className="h-4 w-36" />
              <Bone className="h-3 w-20" />
            </div>
            <Bone className="h-4 w-16" />
          </div>
        ))}
        <div className="flex justify-end">
          <Bone className="h-5 w-24" />
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <Bone className="h-9 w-28 rounded-lg" />
        <Bone className="h-9 w-24 rounded-lg" />
      </div>

      {/* Quick links */}
      <div className="flex gap-2 overflow-hidden">
        {[1, 2, 3].map(i => (
          <Bone key={i} className="h-8 w-28 rounded-full shrink-0" />
        ))}
      </div>
    </div>
  )
}

// ── Page Skeleton: List with rich cards (border-l-4) ─────────────────────────
// FilterBar + Cards(n) with badge, reference, details

export function ListCardSkeleton({ cards = 6, withFilter = true }: { cards?: number; withFilter?: boolean }) {
  return (
    <div className="space-y-4 animate-pulse">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Bone className="h-6 w-36" />
        <Bone className="h-9 w-9 rounded-lg" />
      </div>

      {/* Filter bar */}
      {withFilter && (
        <div className="flex gap-2 overflow-hidden">
          {[1, 2, 3, 4].map(i => (
            <BonePill key={i} className={i === 1 ? 'bg-dark-700' : ''} />
          ))}
        </div>
      )}

      {/* Search */}
      <Bone className="h-10 w-full rounded-lg" />

      {/* Cards */}
      <div className="space-y-3">
        {Array.from({ length: cards }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border border-dark-700 border-l-4 border-l-dark-600 bg-dark-900 p-4 space-y-3"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 space-y-2">
                <div className="flex items-center gap-3">
                  <Bone className="h-4 w-24" />
                  <BonePill />
                </div>
                <Bone className="h-3 w-48" />
              </div>
              <Bone className="h-5 w-20" />
            </div>
            <div className="flex items-center gap-4">
              <Bone className="h-3 w-20" />
              <Bone className="h-3 w-24" />
              <Bone className="h-3 w-16" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Page Skeleton: Detail page (hero + tabs + sections) ──────────────────────

export function DetailPageSkeleton({ sections = 3 }: { sections?: number }) {
  return (
    <div className="space-y-4 animate-pulse">
      {/* Hero / header */}
      <div className="rounded-xl border border-dark-700 p-4 space-y-3">
        <Bone className="h-3 w-32" />
        <div className="flex items-center justify-between">
          <Bone className="h-6 w-44" />
          <BonePill />
        </div>
        <div className="flex items-center gap-3">
          <BoneCircle size="w-8 h-8" />
          <Bone className="h-4 w-32" />
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-4 border-b border-dark-700 pb-2">
        <Bone className="h-4 w-16" />
        <Bone className="h-4 w-20" />
        <Bone className="h-4 w-16" />
      </div>

      {/* Content sections */}
      {Array.from({ length: sections }).map((_, i) => (
        <div key={i} className="card p-4 space-y-3">
          <Bone className="h-4 w-32" />
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Bone className="h-3 w-16" />
              <Bone className="h-4 w-28" />
            </div>
            <div className="space-y-2">
              <Bone className="h-3 w-16" />
              <Bone className="h-4 w-24" />
            </div>
          </div>
        </div>
      ))}

      {/* Action buttons */}
      <div className="flex gap-2">
        <Bone className="h-10 w-32 rounded-lg" />
        <Bone className="h-10 w-28 rounded-lg" />
      </div>
    </div>
  )
}

// ── Page Skeleton: Product card grid ─────────────────────────────────────────

export function ProductGridSkeleton({ cards = 6 }: { cards?: number }) {
  return (
    <div className="space-y-4 animate-pulse">
      {/* Header + filter */}
      <div className="flex items-center justify-between">
        <Bone className="h-6 w-36" />
        <Bone className="h-9 w-9 rounded-lg" />
      </div>
      <div className="flex gap-2">
        {[1, 2, 3].map(i => <BonePill key={i} />)}
      </div>
      <Bone className="h-10 w-full rounded-lg" />

      {/* Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {Array.from({ length: cards }).map((_, i) => (
          <div key={i} className="rounded-2xl overflow-hidden bg-dark-900 border border-dark-700">
            <ImagePlaceholder className="h-36 w-full rounded-none" />
            <div className="p-4 space-y-2">
              <Bone className="h-3 w-3/4" />
              <Bone className="h-2 w-1/2" />
              <div className="flex justify-between mt-4">
                <Bone className="h-4 w-16" />
                <BonePill className="h-4 w-12" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Page Skeleton: Operation page (checklist-style) ──────────────────────────

export function OperationSkeleton({ items = 4 }: { items?: number }) {
  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-pulse">
      {/* Header with back + title */}
      <div className="flex items-center gap-4">
        <div className="w-9 h-9 bg-dark-800 rounded-lg" />
        <div className="space-y-2 flex-1">
          <Bone className="h-5 w-48" />
          <Bone className="h-3 w-32" />
        </div>
      </div>

      {/* Progress bar */}
      <Bone className="h-2 w-full rounded-full" />

      {/* Item cards */}
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} className="card p-4 space-y-4">
          <div className="flex items-center justify-between">
            <Bone className="h-4 w-40" />
            <BonePill />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Bone className="h-9 rounded" />
            <Bone className="h-9 rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Page Skeleton: Form page ─────────────────────────────────────────────────

export function FormSkeleton({ fields = 6 }: { fields?: number }) {
  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-pulse">
      <Bone className="h-7 w-48" />
      <div className="card p-4 space-y-4">
        {Array.from({ length: fields }).map((_, i) => (
          <div key={i} className="space-y-1">
            <Bone className="h-3 w-24" />
            <Bone className="h-10 w-full rounded-lg" />
          </div>
        ))}
      </div>
      <div className="flex gap-2 justify-end">
        <Bone className="h-10 w-24 rounded-lg" />
        <Bone className="h-10 w-32 rounded-lg" />
      </div>
    </div>
  )
}

// ── Page Skeleton: Dashboard ─────────────────────────────────────────────────

export function DashboardSkeleton() {
  return (
    <div className="space-y-4 px-4 pt-2 animate-pulse">
      {/* Alert banner */}
      <Bone className="h-16 w-full rounded-2xl" />
      {/* Search */}
      <Bone className="h-11 w-full rounded-xl" />
      {/* Today cards row */}
      <div className="flex gap-4 overflow-hidden">
        {[1, 2, 3].map(i => (
          <div key={i} className="shrink-0 w-40 h-24 bg-dark-800 rounded-xl border border-dark-700" />
        ))}
      </div>
      {/* Quick actions */}
      <div className="grid grid-cols-3 gap-2">
        {[1, 2, 3].map(i => (
          <Bone key={i} className="h-16 rounded-xl" />
        ))}
      </div>
      {/* Feed items */}
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="flex items-start gap-3">
            <BoneCircle size="w-2 h-2" />
            <div className="flex-1 space-y-1">
              <Bone className="h-3 w-40" />
              <Bone className="h-2.5 w-24" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Page Skeleton: Planning / Calendar ────────────────────────────────────────

export function PlanningSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      {/* Date nav */}
      <div className="flex items-center justify-between">
        <Bone className="h-8 w-8 rounded-lg" />
        <Bone className="h-5 w-32" />
        <Bone className="h-8 w-8 rounded-lg" />
      </div>
      {/* Day headers */}
      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: 7 }).map((_, i) => (
          <Bone key={i} className="h-4 rounded" />
        ))}
      </div>
      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: 35 }).map((_, i) => (
          <div key={i} className="h-20 bg-dark-900 rounded-lg border border-dark-700 p-1">
            <Bone className="h-3 w-4" />
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Page Skeleton: Settings / Admin ──────────────────────────────────────────

export function SettingsSkeleton({ groups = 3 }: { groups?: number }) {
  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-pulse">
      <Bone className="h-7 w-40" />
      {Array.from({ length: groups }).map((_, g) => (
        <div key={g} className="card p-4 space-y-4">
          <Bone className="h-5 w-32" />
          {[1, 2, 3].map(i => (
            <div key={i} className="flex items-center justify-between py-2">
              <div className="space-y-1">
                <Bone className="h-4 w-36" />
                <Bone className="h-3 w-52" />
              </div>
              <Bone className="h-6 w-11 rounded-full" />
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

// ── Page Skeleton: Profile ───────────────────────────────────────────────────

export function ProfileSkeleton() {
  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-pulse">
      {/* Avatar + name */}
      <div className="flex items-center gap-4">
        <BoneCircle size="w-16 h-16" />
        <div className="space-y-2">
          <Bone className="h-5 w-36" />
          <Bone className="h-3 w-24" />
        </div>
      </div>
      {/* Form fields */}
      <div className="card p-4 space-y-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="space-y-1">
            <Bone className="h-3 w-20" />
            <Bone className="h-10 w-full rounded-lg" />
          </div>
        ))}
      </div>
      <Bone className="h-10 w-32 rounded-lg" />
    </div>
  )
}

// ── Page Skeleton: Invoice / Financial detail ────────────────────────────────

export function InvoiceDetailSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Bone className="h-6 w-36" />
          <Bone className="h-3 w-24" />
        </div>
        <BonePill />
      </div>

      {/* Amount card */}
      <div className="card p-4 flex items-center justify-between">
        <div className="space-y-1">
          <Bone className="h-3 w-20" />
          <Bone className="h-7 w-28" />
        </div>
        <Bone className="h-2 w-32 rounded-full" />
      </div>

      {/* Line items */}
      <div className="card p-4 space-y-3">
        <Bone className="h-4 w-20" />
        {[1, 2, 3].map(i => (
          <div key={i} className="flex items-center justify-between py-2 border-b border-dark-700 last:border-0">
            <div className="space-y-1">
              <Bone className="h-4 w-40" />
              <Bone className="h-3 w-20" />
            </div>
            <Bone className="h-4 w-16" />
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <Bone className="h-10 w-32 rounded-lg" />
        <Bone className="h-10 w-28 rounded-lg" />
      </div>
    </div>
  )
}
