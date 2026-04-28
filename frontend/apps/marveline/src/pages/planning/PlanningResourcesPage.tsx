import { useState } from 'react'
import { ChevronLeft, ChevronRight, Users } from 'lucide-react'
import { usePlanningResources } from '@/api/queries/usePlanning'

function toISODate(d: Date) {
  return d.toISOString().split('T')[0]
}

const STATUS_COLORS: Record<string, string> = {
  confirmed: 'bg-green-900/30 text-green-400 border-green-700/30',
  pre_check: 'bg-green-900/30 text-green-400 border-green-700/30',
  delivered: 'bg-blue-900/30 text-blue-400 border-blue-700/30',
  extended: 'bg-amber-900/30 text-amber-400 border-amber-700/30',
}

const STATUS_LABELS: Record<string, string> = {
  confirmed: 'Confirmé',
  pre_check: 'Pré-check',
  delivered: 'Livré',
  extended: 'Prolongé',
}

export default function PlanningResourcesPage() {
  const [date, setDate] = useState(toISODate(new Date()))
  const { data, isLoading } = usePlanningResources(date)

  const prevDay = () => {
    const d = new Date(date)
    d.setDate(d.getDate() - 1)
    setDate(toISODate(d))
  }
  const nextDay = () => {
    const d = new Date(date)
    d.setDate(d.getDate() + 1)
    setDate(toISODate(d))
  }

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold flex items-center gap-2 min-w-0">
          <Users className="w-5 h-5 text-gold-400" />
          Ressources actives
        </h1>
        <div className="flex items-center gap-4">
          <button onClick={prevDay} aria-label="Jour précédent" className="p-2 hover:bg-dark-600 rounded text-dark-400">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="text-sm font-medium">
            {new Date(date).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </span>
          <button onClick={nextDay} aria-label="Jour suivant" className="p-2 hover:bg-dark-600 rounded text-dark-400">
            <ChevronRight className="w-5 h-5" />
          </button>
          <button
            onClick={() => setDate(toISODate(new Date()))}
            className="text-xs text-gold-400 hover:text-gold-300 px-4 py-1.5 border border-gold-500/30 rounded-lg bg-dark-900"
          >
            Aujourd'hui
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4 animate-pulse">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-4 space-y-2">
              <div className="h-3 skel rounded w-36" />
              <div className="flex gap-2">
                {Array.from({ length: 3 }).map((_, j) => <div key={j} className="h-5 bg-dark-900 rounded w-20" />)}
              </div>
            </div>
          ))}
        </div>
      ) : !data || data.active_reservations.length === 0 ? (
        <div className="card text-center py-10">
          <Users className="w-10 h-10 text-dark-500 mx-auto mb-4" />
          <p className="font-medium">Aucune ressource active ce jour</p>
          <p className="text-dark-400 text-sm mt-1">Toutes les réservations sont rentrées ou planifiées plus tard</p>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-dark-400">
            <span className="font-semibold">{data.total}</span> réservation(s) active(s)
          </p>
          {data.active_reservations.map((r) => (
            <div key={r.id} className="card flex items-start justify-between gap-4">
              <div>
                <p className="font-medium text-sm">{r.event_name ?? r.reference}</p>
                <p className="text-xs text-dark-400 mt-0.5">
                  Ref: {r.reference}
                  {r.event_date && ` · Départ: ${new Date(r.event_date).toLocaleDateString('fr-FR')}`}
                  {r.return_date && ` · Retour: ${new Date(r.return_date).toLocaleDateString('fr-FR')}`}
                </p>
              </div>
              <span
                className={`text-xs px-2 py-0.5 rounded-full border shrink-0 ${
                  STATUS_COLORS[r.status] ?? 'bg-dark-900 text-dark-300 border-dark-600'
                }`}
              >
                {STATUS_LABELS[r.status] ?? r.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
