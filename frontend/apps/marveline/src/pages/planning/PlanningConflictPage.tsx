import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { AlertTriangle, Calendar, ChevronLeft, ChevronRight } from 'lucide-react'
import { usePlanningMonth } from '@/api/queries/usePlanning'
import { normalizeError } from '@shared/errors/normalizer'

function toISODate(d: Date) {
  return d.toISOString().split('T')[0]
}

function getMonthStart(year: number, month: number) {
  return toISODate(new Date(year, month, 1))
}

const STATUS_COLORS: Record<string, string> = {
  confirmed: 'bg-green-900/40 text-green-300',
  confirmed_risk: 'bg-red-900/40 text-red-300',
  pre_check: 'bg-green-900/40 text-green-300',
  delivered: 'bg-blue-900/40 text-blue-300',
  extended: 'bg-blue-900/40 text-blue-300',
  returned: 'bg-dark-900 text-dark-300',
  returned_dispute: 'bg-orange-900/40 text-orange-300',
  completed: 'bg-dark-900 text-dark-300',
  cancelled: 'bg-red-900/40 text-red-300',
  draft: 'bg-dark-900 text-dark-400',
}

export default function PlanningConflictPage() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth())

  const monthStr = getMonthStart(year, month)
  const { data, isLoading, error } = usePlanningMonth(monthStr)

  const prevMonth = () => {
    if (month === 0) { setYear(y => y - 1); setMonth(11) }
    else { setMonth(m => m - 1) }
  }

  const nextMonth = () => {
    if (month === 11) { setYear(y => y + 1); setMonth(0) }
    else { setMonth(m => m + 1) }
  }

  const monthLabel = new Date(year, month, 1).toLocaleDateString('fr-FR', {
    month: 'long',
    year: 'numeric',
  })

  // ── Détection des conflits ────────────────────────────────────────────────
  // Conflit = plusieurs réservations actives qui se chevauchent sur la même date
  const conflicts = (() => {
    if (!data) return []
    const active = data.reservations.filter(r => r.status !== 'cancelled')
    const byDate = new Map<string, typeof active>()

    active.forEach(resa => {
      const start = new Date(resa.event_date)
      const end = new Date(resa.return_date ?? resa.event_date)
      const d = new Date(start)
      while (d <= end) {
        const key = toISODate(d)
        const list = byDate.get(key) ?? []
        list.push(resa)
        byDate.set(key, list)
        d.setDate(d.getDate() + 1)
      }
    })

    return Array.from(byDate.entries())
      .filter(([, resas]) => resas.length > 1)
      .sort(([a], [b]) => a.localeCompare(b))
  })()

  // ── Loading skeleton ───────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4 animate-pulse">
        {/* Month nav placeholder */}
        <div className="flex items-center justify-between gap-3">
          <div className="w-8 h-8 bg-dark-800 rounded-lg" />
          <div className="h-5 bg-dark-800 rounded w-32" />
          <div className="w-8 h-8 bg-dark-800 rounded-lg" />
        </div>
        {/* KPI row */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="card p-4 space-y-2">
              <div className="h-3 bg-dark-800 rounded w-16" />
              <div className="h-6 bg-dark-800 rounded w-10" />
            </div>
          ))}
        </div>
        {/* Conflict cards */}
        {[1, 2, 3].map(i => (
          <div key={i} className="card p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="h-4 bg-dark-800 rounded w-32" />
              <div className="h-5 w-20 bg-dark-800 rounded-full" />
            </div>
            <div className="h-3 bg-dark-800 rounded w-56" />
            <div className="flex gap-2">
              <div className="h-3 bg-dark-800 rounded w-20" />
              <div className="h-3 bg-dark-800 rounded w-24" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  // ── Error ──────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="max-w-3xl mx-auto card p-8 text-center text-danger">
        {normalizeError(error).message}
      </div>
    )
  }

  // ── Main view ──────────────────────────────────────────────────────────────
  return (
    <div className="max-w-3xl mx-auto space-y-4 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <h1 className="text-lg font-semibold flex items-center gap-2 flex-1 min-w-0">
          <AlertTriangle className="w-5 h-5 text-yellow-400" />
          Conflits de planning
        </h1>
        <div className="flex items-center gap-2">
          <button
            onClick={prevMonth}
            aria-label="Mois précédent"
            className="p-2 hover:bg-dark-600 rounded min-h-[44px] min-w-[44px] flex items-center justify-center"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-dark-200 min-w-[120px] text-center capitalize">
            {monthLabel}
          </span>
          <button
            onClick={nextMonth}
            aria-label="Mois suivant"
            className="p-2 hover:bg-dark-600 rounded min-h-[44px] min-w-[44px] flex items-center justify-center"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Résumé */}
      <div className="card p-4 flex items-center gap-4 text-sm">
        <div className="text-dark-400">
          Réservations actives : <span className="text-dark-100 font-medium">{data?.total_reservations ?? 0}</span>
        </div>
        <div className={conflicts.length > 0 ? 'text-yellow-400 font-medium' : 'text-green-400'}>
          {conflicts.length === 0
            ? '✓ Aucun conflit détecté'
            : `${conflicts.length} jour${conflicts.length > 1 ? 's' : ''} en conflit`}
        </div>
      </div>

      {/* Liste des conflits */}
      {conflicts.length === 0 ? (
        <div className="card p-10 text-center">
          <Calendar className="w-10 h-10 text-green-400 mx-auto mb-4" />
          <p className="text-dark-300 font-medium">Aucun chevauchement ce mois-ci</p>
          <p className="text-sm text-dark-500 mt-1">
            Toutes les réservations actives sont compatibles.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {conflicts.map(([date, resas]) => (
            <div key={date} className="card p-4">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-4 h-4 text-yellow-400 shrink-0" />
                <span className="text-sm font-semibold text-yellow-300">
                  {new Date(date).toLocaleDateString('fr-FR', {
                    weekday: 'long',
                    day: 'numeric',
                    month: 'long',
                  })}
                </span>
                <span className="text-xs text-dark-500 ml-auto">
                  {resas.length} réservations
                </span>
              </div>
              <div className="space-y-2">
                {resas.map(r => (
                  <Link
                    key={r.id}
                    to="/planning/event/$id"
                    params={{ id: String(r.id) }}
                    className="flex items-center justify-between px-4 py-2 rounded-lg bg-dark-900 hover:bg-dark-600 transition-colors"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm font-medium text-dark-200 truncate">
                        {r.reference}
                      </span>
                      {r.event_name && (
                        <span className="text-xs text-dark-500 truncate hidden sm:block">
                          — {r.event_name}
                        </span>
                      )}
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ml-2 ${STATUS_COLORS[r.status] ?? 'bg-dark-900 text-dark-400'}`}>
                      {r.status}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
