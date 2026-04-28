import { useState } from 'react'
import { useParams } from '@tanstack/react-router'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import { useProductAvailability, useProductDetail } from '@/api/queries'
import type { ProductAvailabilitySlot } from '@/types/product'
import { cn } from '@/lib/utils'
import { ErrorState } from '@shared/components/ui/EmptyState'

// ── Helpers ─────────────────────────────────────────────────────────────────

function getDaysInMonth(year: number, month: number): Date[] {
  const days: Date[] = []
  const date = new Date(year, month, 1)
  while (date.getMonth() === month) {
    days.push(new Date(date))
    date.setDate(date.getDate() + 1)
  }
  return days
}

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function isoToDate(s: string): Date {
  const [y, m, day] = s.split('-').map(Number)
  return new Date(y, m - 1, day)
}

function reservedOnDay(day: Date, slots: ProductAvailabilitySlot[]): number {
  const d = toISODate(day)
  return slots
    .filter((s) => s.date_from <= d && s.date_to >= d)
    .reduce((sum, s) => sum + s.reserved_quantity, 0)
}

type DayStatus = 'available' | 'partial' | 'full' | 'past'

function getDayStatus(day: Date, slots: ProductAvailabilitySlot[], total: number): DayStatus {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  if (day < today) return 'past'
  const reserved = reservedOnDay(day, slots)
  if (reserved === 0) return 'available'
  if (reserved >= total) return 'full'
  return 'partial'
}

const STATUS_STYLE: Record<DayStatus, string> = {
  available: 'bg-green-500/20 text-green-300 hover:bg-green-500/30',
  partial:   'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30',
  full:      'bg-red-500/20 text-red-400 hover:bg-red-500/30',
  past:      'text-dark-500 opacity-40 cursor-default',
}

const WEEKDAYS   = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const MONTH_NAMES = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

// ── Component ────────────────────────────────────────────────────────────────

export default function ProductAvailabilityCalendarPage() {
  const { id } = useParams({ from: '/_app/catalogue/products/$id/availability' })
  const productId = Number(id)

  const now = new Date()
  const [year,  setYear]  = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth())

  const { data: product } = useProductDetail(productId)
  const dateFrom = toISODate(new Date(year, month, 1))
  const dateTo = toISODate(new Date(year, month + 1, 0))

  const {
    data: availability,
    isLoading,
    error,
    refetch,
  } = useProductAvailability(!isNaN(productId) ? productId : null, dateFrom, dateTo)

  const slots    = availability?.busy_slots ?? []
  const totalQty = availability?.total_quantity ?? 0

  const days          = getDaysInMonth(year, month)
  const firstDayOfWeek = (new Date(year, month, 1).getDay() + 6) % 7
  const blanks        = Array(firstDayOfWeek).fill(null)

  const prevMonth = () => {
    if (month === 0) { setYear(y => y - 1); setMonth(11) }
    else setMonth(m => m - 1)
  }

  const nextMonth = () => {
    if (month === 11) { setYear(y => y + 1); setMonth(0) }
    else setMonth(m => m + 1)
  }

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <BackButton />
        <div>
          <h1 className="text-xl font-bold">
            Disponibilité — {product?.name ?? `Produit #${productId}`}
          </h1>
          {totalQty > 0 && (
            <p className="text-sm text-dark-400">Stock total : {totalQty} unité{totalQty > 1 ? 's' : ''}</p>
          )}
        </div>
      </div>

      {/* Navigation mois */}
      <div className="flex items-center justify-between card px-4 py-4">
        <button onClick={prevMonth} aria-label="Mois précédent" className="p-2 rounded-lg hover:bg-dark-600 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center">
          <ChevronLeft className="w-5 h-5" />
        </button>
        <span className="text-base font-semibold">
          {MONTH_NAMES[month]} {year}
        </span>
        <button onClick={nextMonth} aria-label="Mois suivant" className="p-2 rounded-lg hover:bg-dark-600 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center">
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      {error && <ErrorState onRetry={() => refetch()} />}

      {/* Calendrier */}
      <div className="card p-0 overflow-hidden">
        {/* En-têtes jours */}
        <div className="grid grid-cols-7 border-b border-dark-600">
          {WEEKDAYS.map((d) => (
            <div key={d} className="py-2 text-center text-xs font-medium text-dark-400 uppercase">
              {d}
            </div>
          ))}
        </div>

        {/* Skeleton ou grille */}
        {isLoading ? (
          <div className="grid grid-cols-7 gap-px">
            {Array.from({ length: 35 }).map((_, i) => (
              <div key={i} className="min-h-[52px] bg-dark-900 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-7 gap-px bg-dark-900">
            {blanks.map((_, i) => (
              <div key={`b${i}`} className="bg-dark-900 min-h-[52px]" />
            ))}
            {days.map((day) => {
              const status   = getDayStatus(day, slots, totalQty)
              const reserved = reservedOnDay(day, slots)
              const isToday  = toISODate(day) === toISODate(now)

              return (
                <div
                  key={toISODate(day)}
                  className={cn(
                    'bg-dark-900 min-h-[52px] p-1.5 flex flex-col items-center gap-0.5',
                    STATUS_STYLE[status],
                    isToday && 'ring-1 ring-inset ring-primary-500',
                  )}
                >
                  <span className={cn('text-sm font-medium', isToday && 'text-primary-400')}>
                    {day.getDate()}
                  </span>
                  {status !== 'past' && reserved > 0 && (
                    <span className="text-[10px] font-medium opacity-80">
                      {reserved}/{totalQty}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Légende */}
      <div className="flex flex-wrap gap-4 text-xs text-dark-400">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-green-500/30 inline-block" />
          Disponible
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-amber-500/30 inline-block" />
          Partiellement réservé
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-red-500/30 inline-block" />
          Complet
        </span>
      </div>

      {/* Détail créneaux occupés */}
      {slots.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Réservations du mois</h3>
          <div className="card p-0 overflow-hidden divide-y divide-dark-600">
            {slots
              .filter((s) => {
                const monthStr = `${year}-${String(month + 1).padStart(2, '0')}`
                return (
                  s.date_from.startsWith(monthStr) ||
                  s.date_to.startsWith(monthStr) ||
                  (s.date_from <= `${monthStr}-01` && s.date_to >= `${monthStr}-31`)
                )
              })
              .map((s) => (
                <div key={s.reservation_id} className="flex items-center justify-between px-4 py-4">
                  <div>
                    <p className="text-sm font-medium">
                      {s.reservation_ref || `Résa #${s.reservation_id}`}
                    </p>
                    <p className="text-xs text-dark-400">
                      {isoToDate(s.date_from).toLocaleDateString('fr-FR')} →{' '}
                      {isoToDate(s.date_to).toLocaleDateString('fr-FR')}
                    </p>
                  </div>
                  <span className="text-sm font-semibold">×{s.reserved_quantity}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {!isLoading && slots.length === 0 && (
        <p className="text-sm text-dark-400 text-center py-4">
          Aucune réservation ce mois-ci — produit disponible.
        </p>
      )}
    </div>
  )
}
