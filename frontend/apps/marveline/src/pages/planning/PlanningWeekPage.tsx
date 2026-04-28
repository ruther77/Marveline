import { useState } from 'react'
import { ChevronLeft, ChevronRight, Calendar, Package } from 'lucide-react'
import { usePlanningWeek } from '@/api/queries/usePlanning'

function toISODate(d: Date) {
  return d.toISOString().split('T')[0]
}

function getMondayOf(dateStr: string) {
  const d = new Date(dateStr)
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  d.setDate(d.getDate() + diff)
  return toISODate(d)
}

const DAY_NAMES = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

const STATUS_COLORS: Record<string, string> = {
  confirmed: 'badge-green',
  pending:   'badge-yellow',
  cancelled: 'badge-red',
  delivered: 'badge-blue',
  returned:  'badge-muted',
}

export default function PlanningWeekPage() {
  const [currentDate, setCurrentDate] = useState(getMondayOf(toISODate(new Date())))
  const { data, isLoading } = usePlanningWeek(currentDate)

  const prevWeek = () => {
    const d = new Date(currentDate)
    d.setDate(d.getDate() - 7)
    setCurrentDate(toISODate(d))
  }

  const nextWeek = () => {
    const d = new Date(currentDate)
    d.setDate(d.getDate() + 7)
    setCurrentDate(toISODate(d))
  }

  const todayStr = toISODate(new Date())

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header navigation */}
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold flex items-center gap-2 min-w-0">
          <Calendar className="w-5 h-5 text-gold-400" />
          Planning semaine
        </h1>
        <div className="flex items-center gap-4">
          <button onClick={prevWeek} aria-label="Semaine précédente" className="p-2 hover:bg-dark-600 rounded text-dark-400">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="text-sm text-dark-300">
            {data
              ? `${new Date(data.week_start).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })} – ${new Date(data.week_end).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })}`
              : currentDate}
          </span>
          <button onClick={nextWeek} aria-label="Semaine suivante" className="p-2 hover:bg-dark-600 rounded text-dark-400">
            <ChevronRight className="w-5 h-5" />
          </button>
          <button
            onClick={() => setCurrentDate(getMondayOf(todayStr))}
            className="text-xs text-gold-400 hover:text-gold-300 px-4 py-1.5 border border-gold-500/30 rounded-lg bg-dark-900"
          >
            Aujourd'hui
          </button>
        </div>
      </div>

      {/* Stats rapides */}
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
        <div className="grid grid-cols-7 gap-2 animate-pulse">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <div className="h-6 skel rounded" />
              <div className="h-16 skel rounded" />
              <div className="h-16 skel rounded" />
            </div>
          ))}
        </div>
      ) : !data ? null : (
        <div className="grid grid-cols-7 gap-2">
          {Object.entries(data.days).map(([dateKey, day], i) => {
            const isToday = dateKey === todayStr
            const dayDate = new Date(dateKey)
            const hasEvents = day.reservations.length > 0 || day.movements.length > 0
            return (
              <div
                key={dateKey}
                className={`rounded-xl border p-2 min-h-[120px] ${
                  isToday
                    ? 'border-gold-500/50 bg-gold-900/10'
                    : 'border-dark-600 bg-dark-900'
                }`}
              >
                <div className={`text-xs font-semibold mb-2 ${isToday ? 'text-gold-400' : 'text-dark-400'}`}>
                  <span className="block">{DAY_NAMES[i]}</span>
                  <span className={`text-lg ${isToday ? 'text-gold-300' : 'text-white'}`}>
                    {dayDate.getDate()}
                  </span>
                </div>

                {!hasEvents && (
                  <p className="text-xs text-dark-600 italic">—</p>
                )}

                {/* Réservations */}
                {day.reservations.map((r) => (
                  <div
                    key={r.id}
                    className={`text-xs px-1.5 py-1 rounded border mb-1 truncate ${STATUS_COLORS[r.status] ?? 'bg-dark-900 text-dark-300 border-dark-600'}`}
                  >
                    <Calendar className="w-2.5 h-2.5 inline mr-0.5" />
                    {r.event_name ?? r.reference}
                  </div>
                ))}

                {/* Mouvements */}
                {day.movements.map((m) => (
                  <div
                    key={m.id}
                    className="text-xs px-1.5 py-1 rounded border mb-1 badge-blue truncate"
                  >
                    <Package className="w-2.5 h-2.5 inline mr-0.5" />
                    {m.movement_type}
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
