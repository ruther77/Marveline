import { useState } from 'react'
import { useParams, useNavigate, Link } from '@tanstack/react-router'
import { normalizeError } from '@shared/errors/normalizer'
import {
  ArrowLeft, AlertTriangle, CheckCircle, Plus, ChevronRight,
  Clock, MapPin, User, XCircle, ShieldAlert, CalendarClock, FileText
} from 'lucide-react'
import {
  useEvenementDetail,
  useEvenementIncidents,
  useUpdateEventStatus,
  useCloseAction,
  useEventReport,
} from '@/api/queries/useEvenements'
import { DomainStatusBadge } from '@shared/components/ui'
import { DeclareIncidentModal } from './components/DeclareIncidentModal'
import { CreateActionPlanModal } from './components/CreateActionPlanModal'
import { MarkReturnedModal } from './components/MarkReturnedModal'
import { CloseEvenementModal } from './components/CloseEvenementModal'
import { RescheduleModal } from './components/RescheduleModal'
import type { EventStatus } from '@/types/event'

const REPORT_STATUSES: EventStatus[] = ['returned', 'damage', 'closed']
const RESCHEDULE_STATUSES: EventStatus[] = ['planned', 'risk']

const SEVERITY_COLORS: Record<string, string> = {
  low: 'text-yellow-400 bg-yellow-900/20 border-yellow-700/30',
  medium: 'text-orange-400 bg-orange-900/20 border-orange-700/30',
  high: 'text-red-400 bg-red-900/20 border-red-700/30',
  critical: 'text-red-500 bg-red-900/30 border-red-600/40',
}

const SEVERITY_LABELS: Record<string, string> = {
  low: 'Faible', medium: 'Modéré', high: 'Élevé', critical: 'Critique',
}

function SlaBadge({ declaredAt, slaHours }: { declaredAt: string; slaHours: number }) {
  const deadline = new Date(declaredAt).getTime() + slaHours * 3_600_000
  const now = Date.now()
  const remainMs = deadline - now
  const remainH = Math.round(remainMs / 3_600_000)

  if (remainMs <= 0) {
    return <span className="text-xs px-2 py-0.5 rounded-full bg-red-900/30 border border-red-600/40 text-red-400">SLA dépassé</span>
  }
  const color = remainH < slaHours * 0.5
    ? 'bg-orange-900/20 border-orange-700/30 text-orange-400'
    : 'bg-green-900/20 border-green-700/30 text-green-400'
  const label = remainH < 1 ? '< 1h' : remainH < 24 ? `${remainH}h` : `${Math.floor(remainH / 24)}j`
  return <span className={`text-xs px-2 py-0.5 rounded-full border ${color}`}>SLA {label}</span>
}

const STATUS_TRANSITIONS: Record<EventStatus, EventStatus[]> = {
  planned: ['in_progress', 'risk', 'cancelled'],
  risk: ['in_progress', 'cancelled'],
  in_progress: ['returned', 'incident', 'damage'],
  incident: ['in_progress', 'damage', 'returned'],
  returned: ['damage', 'closed'],
  damage: ['closed'],
  cancelled: [],
  closed: [],
}

const STATUS_LABELS: Record<EventStatus, string> = {
  planned: 'Planifié', risk: 'À risque', in_progress: 'En cours',
  incident: 'Incident', returned: 'Retourné', damage: 'Dommage',
  cancelled: 'Annulé', closed: 'Clôturé',
}

// Labels pour les boutons d'action (transitions) — différents des labels d'état
const ACTION_LABELS: Partial<Record<EventStatus, string>> = {
  in_progress: 'Démarrer',
  risk: 'Signaler un risque',
  cancelled: 'Annuler l\'événement',
  returned: 'Marquer retourné',
  damage: 'Déclarer dommage',
  closed: 'Clôturer',
  incident: 'Déclarer incident',
}

const ACTION_ICONS: Partial<Record<EventStatus, React.ElementType>> = {
  risk: ShieldAlert,
  cancelled: XCircle,
}

export default function EvenementDetailPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const navigate = useNavigate()
  const evId = parseInt(id, 10)

  const { data, isLoading, error: queryError, refetch } = useEvenementDetail(evId)
  const { data: incidentsData = [] } = useEvenementIncidents(evId)
  const updateStatus = useUpdateEventStatus(evId)
  const closeAction = useCloseAction(evId)

  const [incidentModal, setIncidentModal] = useState(false)
  const [returnedModal, setReturnedModal] = useState(false)
  const [closeModal, setCloseModal] = useState(false)
  const [rescheduleModal, setRescheduleModal] = useState(false)
  const [reportOpen, setReportOpen] = useState(false)
  const [actionModal, setActionModal] = useState<{ incidentId: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: report } = useEventReport(reportOpen && data ? evId : null)

  const handleStatusChange = (newStatus: EventStatus) => {
    if (newStatus === 'returned') { setReturnedModal(true); return }
    if (newStatus === 'closed') { setCloseModal(true); return }
    if (newStatus === 'incident') { setIncidentModal(true); return }
    if (newStatus === 'damage' && data?.reservation_id) {
      navigate({ to: '/operations/return/$reservationId', params: { reservationId: String(data.reservation_id) } })
      return
    }
    setError(null)
    updateStatus.mutate({ status: newStatus }, {
      onError: (err) => {
        setError(
          normalizeError(err).message || 'Erreur lors de la mise à jour.'
        )
      },
    })
  }

  const handleCloseAction = (incidentId: number, actionId: number) => {
    closeAction.mutate({ incidentId, actionId }, {
      onError: (err) => {
        setError(
          normalizeError(err).message || 'Erreur lors de la clôture.'
        )
      },
    })
  }

  if (isLoading) return (
    <div className="space-y-4 animate-pulse">
      <div className="card p-6 space-y-4">
        <div className="h-5 skel rounded w-48" />
        <div className="h-3 skel rounded w-64" />
      </div>
      <div className="card p-6 space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex justify-between">
            <div className="h-3 skel rounded w-28" />
            <div className="h-3 skel rounded w-36" />
          </div>
        ))}
      </div>
    </div>
  )
  if (queryError) return (
    <div className="card text-center py-12">
      <p className="text-red-400 mb-4">Erreur lors du chargement de l'événement.</p>
      <button onClick={() => refetch()} className="btn-secondary text-sm">Réessayer</button>
    </div>
  )
  if (!data) return <div className="p-6 text-center text-dark-400">Événement introuvable.</div>

  const transitions = STATUS_TRANSITIONS[data.status] ?? []
  const canReschedule = RESCHEDULE_STATUSES.includes(data.status)
  const canViewReport = REPORT_STATUSES.includes(data.status)
  const incidents = incidentsData.length > 0 ? incidentsData : data.incidents
  const openIncidents = incidents.filter((i) => !i.resolved_at)
  const closedIncidents = incidents.filter((i) => !!i.resolved_at)

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => navigate({ to: '/evenements' })}
          aria-label="Retour aux événements"
          className="p-2 hover:bg-dark-600 rounded text-dark-400 shrink-0 mt-0.5"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-semibold">{data.name}</h1>
            <DomainStatusBadge status={data.status} size="md" />
          </div>
          <div className="flex flex-wrap gap-4 mt-1 text-xs text-dark-400">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              {new Date(data.event_date).toLocaleDateString('fr-FR')}
            </span>
            {data.event_location && (
              <span className="flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5" />
                {data.event_location}
              </span>
            )}
            {data.customer_name && (
              <span className="flex items-center gap-1">
                <User className="w-3.5 h-3.5" />
                {data.customer_name}
              </span>
            )}
            {data.reservation_id && (
              <Link
                to="/reservations/$id"
                params={{ id: String(data.reservation_id) }}
                className="flex items-center gap-1 text-primary-400 hover:text-primary-300"
              >
                <FileText className="w-3.5 h-3.5" />
                Réservation #{data.reservation_id}
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Actions secondaires : reprogrammer / rapport */}
      {(canReschedule || canViewReport) && (
        <div className="flex flex-wrap gap-2">
          {canReschedule && (
            <button
              onClick={() => setRescheduleModal(true)}
              className="flex items-center gap-1.5 text-sm text-dark-400 hover:text-dark-50 border border-dark-600 hover:border-dark-500 px-3 py-1.5 rounded-lg transition-colors"
            >
              <CalendarClock className="w-3.5 h-3.5" />
              Reprogrammer
            </button>
          )}
          {canViewReport && (
            <button
              onClick={() => setReportOpen((v) => !v)}
              className="flex items-center gap-1.5 text-sm text-dark-400 hover:text-dark-50 border border-dark-600 hover:border-dark-500 px-3 py-1.5 rounded-lg transition-colors"
            >
              <FileText className="w-3.5 h-3.5" />
              {reportOpen ? 'Masquer le rapport' : 'Rapport de clôture'}
            </button>
          )}
        </div>
      )}

      {/* Rapport de clôture (inline) */}
      {reportOpen && report && (
        <div className="card space-y-4">
          <h2 className="text-sm font-medium text-dark-300 flex items-center gap-2">
            <FileText className="w-4 h-4 text-primary-400" />
            Rapport de clôture
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-center">
            <div className="bg-dark-900/50 rounded-lg p-3">
              <p className="text-lg font-semibold">{report.summary.total_incidents}</p>
              <p className="text-xs text-dark-400">incidents</p>
            </div>
            <div className="bg-dark-900/50 rounded-lg p-3">
              <p className="text-lg font-semibold text-green-400">{report.summary.resolved_incidents}</p>
              <p className="text-xs text-dark-400">résolus</p>
            </div>
            <div className="bg-dark-900/50 rounded-lg p-3">
              <p className="text-lg font-semibold text-red-400">{report.summary.open_incidents}</p>
              <p className="text-xs text-dark-400">ouverts</p>
            </div>
          </div>
          {report.closure_notes && (
            <div className="bg-dark-900/30 rounded-lg px-4 py-3 text-sm text-dark-300 italic">
              {report.closure_notes}
            </div>
          )}
        </div>
      )}

      {/* Machine d'états — transitions */}
      {transitions.length > 0 && (
        <div className="card space-y-2">
          <p className="text-xs text-dark-400 font-medium">Transition de statut</p>
          <div className="flex flex-wrap gap-2">
            {transitions.map((s) => {
              const Icon = ACTION_ICONS[s] ?? ChevronRight
              const isCancelAction = s === 'cancelled'
              return (
                <button
                  key={s}
                  onClick={() => handleStatusChange(s)}
                  disabled={updateStatus.isPending}
                  className={`flex items-center gap-1.5 border text-sm px-4 py-1.5 rounded-lg disabled:opacity-50 transition-colors ${
                    isCancelAction
                      ? 'btn-danger'
                      : 'btn-secondary'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isCancelAction ? '' : 'text-gold-400'}`} />
                  {ACTION_LABELS[s] ?? STATUS_LABELS[s]}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-900/20 border border-red-700 rounded-lg px-4 py-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Incidents ouverts */}
      <div className="card space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-medium text-dark-300 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Incidents actifs
            {openIncidents.length > 0 && (
              <span className="bg-red-900/30 text-red-400 text-xs px-2 py-0.5 rounded-full">
                {openIncidents.length}
              </span>
            )}
          </h2>
          <button
            onClick={() => setIncidentModal(true)}
            className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300"
          >
            <Plus className="w-3.5 h-3.5" />
            Déclarer
          </button>
        </div>

        {openIncidents.length === 0 ? (
          <p className="text-dark-400 text-sm">Aucun incident actif</p>
        ) : (
          <div className="space-y-4">
            {openIncidents.map((incident) => {
              const incidentActions = incident.actions ?? []
              return (
                <div key={incident.id} className="border border-dark-600 rounded-xl p-4 space-y-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm">{incident.description}</p>
                      <p className="text-dark-400 text-xs mt-0.5">
                        {new Date(incident.declared_at).toLocaleDateString('fr-FR')}
                        {incident.owner_name && <span> · <span className="text-dark-300">{incident.owner_name}</span></span>}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      <span className={`text-xs px-2 py-0.5 rounded-full border ${SEVERITY_COLORS[incident.severity]}`}>
                        {SEVERITY_LABELS[incident.severity]}
                      </span>
                      <SlaBadge declaredAt={incident.declared_at} slaHours={incident.sla_hours} />
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="space-y-2">
                    {incidentActions.map((action) => (
                      <div key={action.id} className="flex items-center justify-between text-xs bg-dark-900/50 rounded-lg px-4 py-2">
                        <div>
                          <p className={action.status === 'done' ? 'text-dark-400 line-through' : 'text-white'}>
                            {action.label}
                          </p>
                          <p className="text-dark-500">
                            {action.assignee_name ?? `#${action.assignee_id}`} · échéance {new Date(action.deadline).toLocaleDateString('fr-FR')}
                          </p>
                        </div>
                        {action.status !== 'done' && (
                          <button
                            onClick={() => handleCloseAction(incident.id, action.id)}
                            disabled={closeAction.isPending}
                            className="text-green-400 hover:text-green-300 ml-2 shrink-0"
                            title="Marquer fait"
                          >
                            <CheckCircle className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    ))}
                    <button
                      onClick={() => setActionModal({ incidentId: incident.id })}
                      className="flex items-center gap-1 text-xs text-dark-400 hover:text-gold-400"
                    >
                      <Plus className="w-3 h-3" />
                      Ajouter une action
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Incidents résolus (collapse) */}
      {closedIncidents.length > 0 && (
        <div className="card space-y-2">
          <h2 className="text-sm font-medium text-dark-400">
            Incidents résolus ({closedIncidents.length})
          </h2>
          <div className="space-y-2">
            {closedIncidents.map((incident) => (
              <div key={incident.id} className="flex items-center justify-between text-sm">
                <p className="text-dark-400 line-through text-xs">{incident.description}</p>
                <span className="text-xs text-green-400">
                  {incident.resolved_at && new Date(incident.resolved_at).toLocaleDateString('fr-FR')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Modals */}
      <DeclareIncidentModal
        open={incidentModal}
        onClose={() => setIncidentModal(false)}
        evenementId={evId}
        onSuccess={() => {
          updateStatus.mutate({ status: 'incident' })
          setIncidentModal(false)
        }}
      />
      {actionModal && (
        <CreateActionPlanModal
          open={true}
          onClose={() => setActionModal(null)}
          evenementId={evId}
          incidentId={actionModal.incidentId}
        />
      )}
      <MarkReturnedModal
        open={returnedModal}
        onClose={() => setReturnedModal(false)}
        evenementId={evId}
        evenementName={data.name}
      />
      <CloseEvenementModal
        open={closeModal}
        onClose={() => setCloseModal(false)}
        evenementId={evId}
        evenementName={data.name}
      />
      <RescheduleModal
        open={rescheduleModal}
        onClose={() => setRescheduleModal(false)}
        evenementId={evId}
        evenementName={data.name}
        currentDate={data.event_date}
      />
    </div>
  )
}
