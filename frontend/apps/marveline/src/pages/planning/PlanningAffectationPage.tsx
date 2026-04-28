import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { ChevronLeft, ChevronRight, ClipboardList, CheckCircle2, Circle, AlertTriangle, UserCheck, UserX } from 'lucide-react'
import { usePlanningWeek } from '@/api/queries/usePlanning'
import { useAssignUser } from '@/api/queries/usePlanning'
import { useUsers } from '@/api/queries/admin/useUsers'
import { Link } from '@tanstack/react-router'
import { normalizeError } from '@shared/errors/normalizer'
import type { User } from '@/types'

function toISODate(d: Date) {
  return d.toISOString().split('T')[0]
}

function getWeekStart(date: Date) {
  const d = new Date(date)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  d.setDate(diff)
  return d
}

const STATUS_LABELS: Record<string, string> = {
  confirmed: 'Confirmé',
  confirmed_risk: 'Risque',
  pre_check: 'Pré-check',
  delivered: 'Livré',
  extended: 'Prolongé',
  pending: 'En attente',
  cancelled: 'Annulé',
}

const READY_STATUSES = ['delivered', 'extended', 'completed']

// ── Sélecteur d'utilisateur inline ──────────────────────────────────────────

interface UserSelectProps {
  reservationId: number
  currentUserId: number | null | undefined
  users: User[]
  weekStr: string
}

function UserSelect({ reservationId, currentUserId, users, weekStr }: UserSelectProps) {
  const assign = useAssignUser(weekStr)
  const [error, setError] = useState<string | null>(null)

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value
    const userId = value === '' ? null : Number(value)
    setError(null)
    assign.mutate(
      { reservationId, userId },
      {
        onError: (err) => setError(normalizeError(err).message || 'Erreur d\'affectation'),
      }
    )
  }

  return (
    <div className="shrink-0 flex flex-col items-end gap-1 min-w-[160px]">
      <select
        value={currentUserId ?? ''}
        onChange={handleChange}
        disabled={assign.isPending}
        className="text-xs bg-dark-900 border border-dark-600 text-dark-200 rounded-lg px-2 py-1.5 pr-6 appearance-none hover:border-dark-500 focus:border-primary-500 focus:outline-none disabled:opacity-50 cursor-pointer min-w-[150px]"
      >
        <option value="">— Non assigné —</option>
        {users.map((u) => (
          <option key={u.id} value={u.id}>
            {u.full_name || u.email}
          </option>
        ))}
      </select>
      {error && <p className="text-red-400 text-xs">{error}</p>}
    </div>
  )
}

// ── Page principale ──────────────────────────────────────────────────────────

export default function PlanningAffectationPage() {
  const [weekStart, setWeekStart] = useState(() => getWeekStart(new Date()))
  const weekStr = toISODate(weekStart)
  const { data, isLoading } = usePlanningWeek(weekStr)

  // Charger les utilisateurs du tenant pour le sélecteur d'affectation
  const { data: usersData } = useUsers({ limit: 100 })
  const users: User[] = usersData?.items ?? []

  const prevWeek = () => {
    const d = new Date(weekStart)
    d.setDate(d.getDate() - 7)
    setWeekStart(d)
  }
  const nextWeek = () => {
    const d = new Date(weekStart)
    d.setDate(d.getDate() + 7)
    setWeekStart(d)
  }

  const allReservations = data
    ? Object.values(data.days).flatMap((day) =>
        day.reservations.map((r) => ({ ...r, dayDate: '' }))
      )
    : []

  // Déduplique par ID
  const seen = new Set<number>()
  const reservations = allReservations.filter((r) => {
    if (seen.has(r.id)) return false
    seen.add(r.id)
    return true
  })

  const weekEnd = new Date(weekStart)
  weekEnd.setDate(weekEnd.getDate() + 6)

  const formatWeekRange = () => {
    const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' }
    return `${weekStart.toLocaleDateString('fr-FR', opts)} — ${weekEnd.toLocaleDateString('fr-FR', opts)}`
  }

  const confirmed = reservations.filter((r) => r.status === 'confirmed').length
  const ready = reservations.filter((r) => READY_STATUSES.includes(r.status)).length
  const assigned = reservations.filter((r) => r.assigned_user_id).length

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <ClipboardList className="w-5 h-5 text-gold-400" />
          <PageHeader title="Affectation des ressources" />
        </div>
        <div className="flex items-center gap-2">
          <button onClick={prevWeek} aria-label="Semaine précédente" className="p-2 hover:bg-dark-600 rounded text-dark-400">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-dark-300 w-44 text-center">{formatWeekRange()}</span>
          <button onClick={nextWeek} aria-label="Semaine suivante" className="p-2 hover:bg-dark-600 rounded text-dark-400">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold">{reservations.length}</p>
          <p className="text-xs text-dark-400 mt-0.5">Réservations</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold text-amber-400">{confirmed}</p>
          <p className="text-xs text-dark-400 mt-0.5">À préparer</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold text-green-400">{ready}</p>
          <p className="text-xs text-dark-400 mt-0.5">Prêtes</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold text-primary-400">{assigned}</p>
          <p className="text-xs text-dark-400 mt-0.5">Assignées</p>
        </div>
      </div>

      {/* Liste */}
      {isLoading ? (
        <div className="space-y-4 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card p-4 flex items-center gap-4">
              <div className="w-10 h-10 skel rounded-lg shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-40" />
                <div className="h-2 skel rounded w-56" />
              </div>
              <div className="h-7 skel rounded w-36 shrink-0" />
            </div>
          ))}
        </div>
      ) : reservations.length === 0 ? (
        <div className="card text-center py-14">
          <ClipboardList className="w-10 h-10 text-dark-500 mx-auto mb-4" />
          <p className="font-medium">Aucune réservation cette semaine</p>
        </div>
      ) : (
        <div className="card divide-y divide-dark-600">
          {reservations.map((r) => {
            const isReady = READY_STATUSES.includes(r.status)
            const isPending = r.status === 'confirmed'
            return (
              <div key={r.id} className="px-4 py-4 flex items-center gap-4">
                {/* Icône statut */}
                <div className="shrink-0">
                  {isReady ? (
                    <CheckCircle2 className="w-5 h-5 text-green-400" />
                  ) : isPending ? (
                    <AlertTriangle className="w-5 h-5 text-amber-400" />
                  ) : (
                    <Circle className="w-5 h-5 text-dark-500" />
                  )}
                </div>

                {/* Info réservation */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium font-mono">{r.reference}</span>
                    {r.event_name && (
                      <span className="text-dark-400 text-xs">· {r.event_name}</span>
                    )}
                    {r.event_type && (
                      <span className="text-xs bg-dark-900 text-dark-300 px-2 py-0.5 rounded-full">
                        {r.event_type}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 mt-0.5">
                    <span className="text-dark-400 text-xs">
                      {new Date(r.event_date).toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' })}
                    </span>
                    {r.guest_count && (
                      <span className="text-dark-500 text-xs">{r.guest_count} invités</span>
                    )}
                    {/* Indicateur assigné */}
                    {r.assigned_user_id ? (
                      <span className="inline-flex items-center gap-1 text-xs text-primary-400">
                        <UserCheck className="w-3 h-3" />
                        {r.assigned_user_name ?? `#${r.assigned_user_id}`}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-dark-500">
                        <UserX className="w-3 h-3" />
                        Non assigné
                      </span>
                    )}
                  </div>
                </div>

                {/* Statut badge + sélecteur utilisateur */}
                <div className="shrink-0 flex items-center gap-4">
                  <span className={`hidden sm:block text-xs px-2 py-0.5 rounded-full ${
                    isReady
                      ? 'bg-green-900/30 text-green-400'
                      : isPending
                        ? 'bg-amber-900/30 text-amber-400'
                        : 'bg-dark-900 text-dark-400'
                  }`}>
                    {STATUS_LABELS[r.status] ?? r.status}
                  </span>

                  <UserSelect
                    reservationId={r.id}
                    currentUserId={r.assigned_user_id}
                    users={users}
                    weekStr={weekStr}
                  />

                  <Link
                    to={`/reservations/${r.id}` as never}
                    className="hidden sm:block text-xs text-primary-400 hover:underline"
                  >
                    →
                  </Link>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
