import { useState } from 'react'
import { ChevronLeft, ChevronRight, Calendar, Package } from 'lucide-react'
import { usePlanningDay } from '@/api/queries/usePlanning'

function toISODate(d: Date) {
  return d.toISOString().split('T')[0]
}

const STATUS_COLORS: Record<string, string> = {
  confirmed: 'bg-green-900/40 text-green-300 border-green-700/40',
  pending: 'bg-yellow-900/40 text-yellow-300 border-yellow-700/40',
  cancelled: 'bg-red-900/40 text-red-300 border-red-700/40',
  delivered: 'bg-blue-900/40 text-blue-300 border-blue-700/40',
  returned: 'bg-dark-900 text-dark-300 border-dark-600',
}

const DAY_NAMES_FULL = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
const MONTHS_FR = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

export default function PlanningDayPage() {
  const [currentDate, setCurrentDate] = useState(toISODate(new Date()))

  const { data, isLoading } = usePlanningDay(currentDate)

  const prevDay = () => {
    const d = new Date(currentDate)
    d.setDate(d.getDate() - 1)
    setCurrentDate(toISODate(d))
  }

  const nextDay = () => {
    const d = new Date(currentDate)
    d.setDate(d.getDate() + 1)
    setCurrentDate(toISODate(d))
  }

  const todayStr = toISODate(new Date())
  const isToday = currentDate === todayStr

  const currentDateObj = new Date(currentDate)
  const dayLabel = `${DAY_NAMES_FULL[currentDateObj.getDay()]} ${currentDateObj.getDate()} ${MONTHS_FR[currentDateObj.getMonth()]} ${currentDateObj.getFullYear()}`

  const reservations = data?.reservations ?? []
  const movements = data?.movements ?? []
  const total = reservations.length + movements.length

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header navigation */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-xl font-semibold flex items-center gap-2 min-w-0">
          <Calendar className="w-5 h-5 text-gold-400" />
          Planning jour
        </h1>
        <div className="flex items-center gap-4">
          <button onClick={prevDay} aria-label="Jour précédent" className="p-2 hover:bg-dark-600 rounded text-dark-400">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className={`text-sm font-medium ${isToday ? 'text-gold-400' : 'text-dark-300'}`}>
            {dayLabel}
          </span>
          <button onClick={nextDay} aria-label="Jour suivant" className="p-2 hover:bg-dark-600 rounded text-dark-400">
            <ChevronRight className="w-5 h-5" />
          </button>
          {!isToday && (
            <button
              onClick={() => setCurrentDate(todayStr)}
              className="text-xs text-gold-400 hover:text-gold-300 px-4 py-1.5 border border-gold-500/30 rounded-lg bg-dark-900"
            >
              Aujourd'hui
            </button>
          )}
        </div>
      </div>

      {/* Stats rapides */}
      <div className="flex gap-4 text-sm">
        <span className="text-dark-400">
          <span className="font-semibold">{data?.total_reservations ?? 0}</span> réservation(s)
        </span>
        <span className="text-dark-400">
          <span className="font-semibold">{data?.total_movements ?? 0}</span> mouvement(s)
        </span>
      </div>

      {/* Contenu */}
      {isLoading ? (
        <div className="space-y-4 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card p-4 flex items-center gap-4">
              <div className="w-10 h-10 skel rounded-lg shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-40" />
                <div className="h-2 skel rounded w-56" />
              </div>
            </div>
          ))}
        </div>
      ) : total === 0 ? (
        <div className="card text-center py-14">
          <Calendar className="w-10 h-10 text-dark-500 mx-auto mb-4" />
          <p className="font-medium">Aucun événement ce jour</p>
          <p className="text-dark-400 text-sm mt-1">Pas de réservation ni de mouvement planifié.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Réservations */}
          {reservations.length > 0 && (
            <div className="card divide-y divide-dark-600">
              <div className="px-4 py-2 text-xs text-dark-400 uppercase tracking-wide font-medium">
                Réservations ({reservations.length})
              </div>
              {reservations.map((r) => (
                <div key={r.id} className="flex items-start gap-4 px-4 py-4">
                  <div
                    className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${
                      r.status === 'confirmed'
                        ? 'bg-green-400'
                        : r.status === 'pending'
                        ? 'bg-yellow-400'
                        : r.status === 'cancelled'
                        ? 'bg-red-400'
                        : 'bg-dark-500'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">
                      {r.event_name ?? r.reference}
                    </p>
                    <div className="flex items-center gap-4 mt-0.5 flex-wrap">
                      <span className="text-dark-400 text-xs">{r.reference}</span>
                      {r.event_type && (
                        <span className="text-dark-500 text-xs capitalize">{r.event_type}</span>
                      )}
                      {r.guest_count != null && (
                        <span className="text-dark-500 text-xs">{r.guest_count} pers.</span>
                      )}
                    </div>
                  </div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full border shrink-0 ${STATUS_COLORS[r.status] ?? 'bg-dark-900 text-dark-300 border-dark-600'}`}
                  >
                    {r.status}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Mouvements */}
          {movements.length > 0 && (
            <div className="card divide-y divide-dark-600">
              <div className="px-4 py-2 text-xs text-dark-400 uppercase tracking-wide font-medium">
                Mouvements ({movements.length})
              </div>
              {movements.map((m) => (
                <div key={m.id} className="flex items-center gap-4 px-4 py-4">
                  <Package className="w-4 h-4 text-blue-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm capitalize">{m.movement_type}</p>
                    {m.reservation_id && (
                      <p className="text-dark-400 text-xs">Réservation #{m.reservation_id}</p>
                    )}
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded-full border bg-blue-900/30 text-blue-300 border-blue-700/30 shrink-0 capitalize">
                    {m.movement_type}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
