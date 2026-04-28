import { useState } from 'react'
import { ChevronLeft, ChevronRight, Calendar, Package } from 'lucide-react'
import { usePlanningMonth } from '@/api/queries/usePlanning'

function toISODate(d: Date) {
  return d.toISOString().split('T')[0]
}

function getMonthStart(year: number, month: number) {
  return `${year}-${String(month).padStart(2, '0')}-01`
}

const MONTH_NAMES = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]
const DAY_HEADERS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

export default function PlanningMonthPage() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)

  const { data, isLoading } = usePlanningMonth(getMonthStart(year, month))

  const prevMonth = () => {
    if (month === 1) { setYear(y => y - 1); setMonth(12) }
    else setMonth(m => m - 1)
  }
  const nextMonth = () => {
    if (month === 12) { setYear(y => y + 1); setMonth(1) }
    else setMonth(m => m + 1)
  }

  const todayStr = toISODate(new Date())

  // Construire la grille calendaire
  const buildGrid = () => {
    const firstDay = new Date(year, month - 1, 1)
    const lastDay = new Date(year, month, 0)
    // Lundi=0...Dimanche=6
    const startOffset = (firstDay.getDay() + 6) % 7
    const cells: (string | null)[] = []
    for (let i = 0; i < startOffset; i++) cells.push(null)
    for (let d = 1; d <= lastDay.getDate(); d++) {
      cells.push(`${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`)
    }
    while (cells.length % 7 !== 0) cells.push(null)
    return cells
  }

  const grid = buildGrid()

  const eventsByDay: Record<string, number> = {}
  const movByDay: Record<string, number> = {}
  if (data) {
    data.reservations.forEach((r) => {
      eventsByDay[r.event_date] = (eventsByDay[r.event_date] ?? 0) + 1
    })
    data.movements.forEach((m) => {
      movByDay[m.scheduled_date] = (movByDay[m.scheduled_date] ?? 0) + 1
    })
  }

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold flex items-center gap-2 min-w-0">
          <Calendar className="w-5 h-5 text-gold-400" />
          Planning mensuel
        </h1>
        <div className="flex items-center gap-4">
          <button onClick={prevMonth} aria-label="Mois précédent" className="p-2 hover:bg-dark-600 rounded text-dark-400">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="text-sm font-medium min-w-[130px] text-center">
            {MONTH_NAMES[month - 1]} {year}
          </span>
          <button onClick={nextMonth} aria-label="Mois suivant" className="p-2 hover:bg-dark-600 rounded text-dark-400">
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Stats */}
      {data && (
        <div className="flex gap-4 text-sm">
          <span className="text-dark-400">
            <span className="font-semibold">{data.total_reservations}</span> réservation(s)
          </span>
          <span className="text-dark-400">
            <span className="font-semibold">{data.total_movements}</span> mouvement(s)
          </span>
        </div>
      )}

      {isLoading ? (
        <div className="card p-4 animate-pulse">
          <div className="grid grid-cols-7 gap-1 mb-1">
            {Array.from({ length: 7 }).map((_, i) => <div key={i} className="h-6 bg-dark-900 rounded" />)}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: 35 }).map((_, i) => <div key={i} className="h-16 bg-dark-900 rounded" />)}
          </div>
        </div>
      ) : (
        <div className="card p-4">
          {/* En-têtes jours */}
          <div className="grid grid-cols-7 mb-2">
            {DAY_HEADERS.map((d) => (
              <div key={d} className="text-center text-xs text-dark-400 font-medium py-1">
                {d}
              </div>
            ))}
          </div>
          {/* Grille */}
          <div className="grid grid-cols-7 gap-1">
            {grid.map((dateKey, i) => {
              if (!dateKey) return <div key={`empty-${i}`} />
              const isToday = dateKey === todayStr
              const evCount = eventsByDay[dateKey] ?? 0
              const mvCount = movByDay[dateKey] ?? 0
              const dayNum = parseInt(dateKey.split('-')[2])
              return (
                <div
                  key={dateKey}
                  className={`rounded-lg p-1.5 min-h-[56px] ${
                    isToday ? 'bg-gold-900/20 border border-gold-500/40' : 'hover:bg-dark-600/30'
                  }`}
                >
                  <p className={`text-xs font-medium mb-1 ${isToday ? 'text-gold-400' : 'text-dark-300'}`}>
                    {dayNum}
                  </p>
                  {evCount > 0 && (
                    <div className="flex items-center gap-0.5 text-xs text-green-400">
                      <Calendar className="w-2.5 h-2.5" />
                      <span>{evCount}</span>
                    </div>
                  )}
                  {mvCount > 0 && (
                    <div className="flex items-center gap-0.5 text-xs text-blue-400">
                      <Package className="w-2.5 h-2.5" />
                      <span>{mvCount}</span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Légende */}
      <div className="flex items-center gap-4 text-xs text-dark-400">
        <span className="flex items-center gap-1"><Calendar className="w-3 h-3 text-green-400" /> Réservation</span>
        <span className="flex items-center gap-1"><Package className="w-3 h-3 text-blue-400" /> Mouvement</span>
      </div>
    </div>
  )
}
