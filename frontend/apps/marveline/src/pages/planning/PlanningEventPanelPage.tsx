import { useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { ArrowLeft, Calendar, Users, MapPin, Package, UserCheck } from 'lucide-react'
import { useReservationDetail } from '@/api/queries/useReservations'
import { useAssignUser } from '@/api/queries/usePlanning'
import { useUsers } from '@/api/queries/useAdmin'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents } from '@/lib/utils'

const STATUS_LABELS: Record<string, string> = {
  draft: 'Brouillon',
  confirmed: 'Confirmée',
  confirmed_risk: 'Confirmée (risque)',
  pre_check: 'Pré-check',
  delivered: 'Livrée',
  extended: 'Prolongée',
  returned: 'Retournée',
  returned_dispute: 'Retournée (litige)',
  completed: 'Terminée',
  cancelled: 'Annulée',
}

const STATUS_COLORS: Record<string, string> = {
  confirmed: 'bg-green-900/40 text-green-300 border-green-700/40',
  confirmed_risk: 'bg-red-900/40 text-red-300 border-red-700/40',
  pre_check: 'bg-green-900/40 text-green-300 border-green-700/40',
  delivered: 'bg-blue-900/40 text-blue-300 border-blue-700/40',
  extended: 'bg-blue-900/40 text-blue-300 border-blue-700/40',
  returned: 'bg-dark-900 text-dark-300 border-dark-600',
  returned_dispute: 'bg-orange-900/40 text-orange-300 border-orange-700/40',
  completed: 'bg-dark-900 text-dark-300 border-dark-600',
  cancelled: 'bg-red-900/40 text-red-300 border-red-700/40',
  draft: 'bg-dark-900 text-dark-400 border-dark-600',
}

export default function PlanningEventPanelPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const resaId = parseInt(id, 10)

  const [assignError, setAssignError] = useState<string | null>(null)
  const [assignSuccess, setAssignSuccess] = useState(false)
  const [lastAssignedId, setLastAssignedId] = useState<number | null | undefined>(undefined)

  const { data: resa, isLoading, error } = useReservationDetail(isNaN(resaId) ? null : resaId)
  const { data: usersData } = useUsers({ limit: 100 })
  const assignMutation = useAssignUser()

  const handleAssign = (userId: number | null) => {
    setAssignError(null)
    setAssignSuccess(false)
    assignMutation.mutate(
      { reservationId: resaId, userId },
      {
        onSuccess: () => {
          setLastAssignedId(userId)
          setAssignSuccess(true)
        },
        onError: (err) => setAssignError(normalizeError(err).message || 'Erreur lors de l\'assignation'),
      }
    )
  }

  // lastAssignedId undefined = pas encore modifié (état inconnu), null = désassigné
  const currentAssigneeId = lastAssignedId !== undefined ? lastAssignedId : null

  // ── Loading skeleton ───────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-4">
        <div className="h-10 w-28 skel rounded animate-pulse" />
        <div className="card p-6 space-y-4">
          <div className="h-6 w-48 skel rounded animate-pulse" />
          <div className="h-4 w-32 skel rounded animate-pulse" />
          <div className="h-4 w-40 skel rounded animate-pulse" />
        </div>
        <div className="card p-6 space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-8 skel rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  // ── ID invalide ────────────────────────────────────────────────────────────
  if (isNaN(resaId)) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto card p-8 text-center text-danger">
        Identifiant de réservation invalide.
      </div>
    )
  }

  // ── Error ──────────────────────────────────────────────────────────────────
  if (error || !resa) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto card p-8 text-center text-danger">
        {error ? normalizeError(error).message : 'Réservation introuvable'}
      </div>
    )
  }

  const statusLabel = STATUS_LABELS[resa.status] ?? resa.status
  const statusColor = STATUS_COLORS[resa.status] ?? 'bg-dark-900 text-dark-300 border-dark-600'
  const staff = usersData?.items ?? []

  // ── Main view ──────────────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-4 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <Link
          to="/planning/week"
          className="btn-secondary btn-sm flex items-center gap-2 min-h-[44px]"
        >
          <ArrowLeft className="w-4 h-4" />
          Planning
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-semibold truncate">{resa.reference}</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full border ${statusColor}`}>
            {statusLabel}
          </span>
        </div>
      </div>

      {/* Infos événement */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">
          Événement
        </h2>
        {resa.event_name && (
          <p className="text-sm font-medium">{resa.event_name}</p>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div className="flex items-center gap-2 text-dark-300">
            <Calendar className="w-4 h-4 text-dark-500 shrink-0" />
            <span>
              Événement : {new Date(resa.event_date).toLocaleDateString('fr-FR')}
            </span>
          </div>
          <div className="flex items-center gap-2 text-dark-300">
            <Calendar className="w-4 h-4 text-dark-500 shrink-0" />
            <span>
              Retour : {new Date(resa.return_date).toLocaleDateString('fr-FR')}
            </span>
          </div>
          {resa.event_location && (
            <div className="flex items-center gap-2 text-dark-300 sm:col-span-2">
              <MapPin className="w-4 h-4 text-dark-500 shrink-0" />
              <span>{resa.event_location}</span>
            </div>
          )}
          {resa.guest_count != null && (
            <div className="flex items-center gap-2 text-dark-300">
              <Users className="w-4 h-4 text-dark-500 shrink-0" />
              <span>{resa.guest_count} invités</span>
            </div>
          )}
        </div>
        {resa.customer_name && (
          <div className="text-sm text-dark-400 border-t border-dark-600 pt-4">
            Client : <span className="text-dark-200">{resa.customer_name}</span>
          </div>
        )}
        <div className="text-sm text-dark-400 border-t border-dark-600 pt-4 flex justify-between">
          <span>Montant total</span>
          <span className="font-semibold text-primary-400">
            {formatCents(resa.total_amount_cents)}
          </span>
        </div>
      </div>

      {/* Lignes */}
      {resa.lines.length > 0 && (
        <div className="card p-6">
          <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide mb-4">
            <Package className="w-3.5 h-3.5 inline mr-1" />
            Articles ({resa.lines.length})
          </h2>
          <div className="space-y-2">
            {resa.lines.map(line => {
              const lineName = line.product?.name ?? `Produit #${line.product_id}`
              return (
                <div key={line.id} className="flex items-center gap-3 text-sm py-1">
                  <div className="w-12 h-12 rounded-lg overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
                    {line.product?.image_url ? (
                      <img src={line.product.image_url} alt={lineName} className="w-full h-full object-cover" loading="lazy" />
                    ) : (
                      <Package className="w-5 h-5 text-dark-600" />
                    )}
                  </div>
                  <span className="text-dark-200 truncate flex-1 min-w-0">
                    {lineName}
                    {line.quantity > 1 && (
                      <span className="text-dark-500 ml-1">×{line.quantity}</span>
                    )}
                  </span>
                  <span className="text-dark-400 tabular-nums shrink-0">
                    {formatCents(line.subtotal_cents)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Assignation */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">
          Responsable assigné
        </h2>

        {currentAssigneeId !== null && (
          <div className="flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-green-400" />
            <span className="text-sm text-dark-100">
              {staff.find(u => u.id === currentAssigneeId)?.full_name ?? `#${currentAssigneeId}`}
            </span>
          </div>
        )}

        {staff.length > 0 && (
          <div>
            <p className="text-xs text-dark-500 mb-2">
              {currentAssigneeId !== null ? 'Changer l\'assigné :' : 'Assigner à :'}
            </p>
            <div className="flex flex-wrap gap-2">
              {staff.map(user => (
                <button
                  key={user.id}
                  onClick={() => handleAssign(user.id)}
                  disabled={assignMutation.isPending || currentAssigneeId === user.id}
                  className={[
                    'px-4 py-1.5 rounded-lg text-sm border min-h-[44px] transition-colors',
                    currentAssigneeId === user.id
                      ? 'bg-primary-500/20 text-primary-400 border-primary-500/40 cursor-default'
                      : 'bg-dark-900 text-dark-300 border-dark-600 hover:bg-dark-600',
                  ].join(' ')}
                >
                  {user.first_name} {user.last_name}
                </button>
              ))}
              {currentAssigneeId !== null && (
                <button
                  onClick={() => handleAssign(null)}
                  disabled={assignMutation.isPending}
                  className="px-4 py-1.5 rounded-lg text-sm border min-h-[44px] text-red-400 border-red-900/40 bg-dark-900 hover:bg-red-900/20 transition-colors"
                >
                  Désassigner
                </button>
              )}
            </div>
          </div>
        )}

        {assignError && (
          <p className="text-sm text-danger">{assignError}</p>
        )}
        {assignSuccess && (
          <p className="text-sm text-green-400">Assignation mise à jour ✓</p>
        )}
      </div>

      {/* Lien détail complet */}
      <div className="flex justify-end">
        <Link
          to="/reservations/$id/phases"
          params={{ id: String(resa.id) }}
          className="btn-secondary btn-sm min-h-[44px]"
        >
          Voir la réservation complète →
        </Link>
      </div>
    </div>
  )
}
