import { PageHeader } from '@/components/PageHeader'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { Search, AlertTriangle, ChevronLeft, ChevronRight } from 'lucide-react'
import { useEvenementsList } from '@/api/queries/useEvenements'
import { DomainStatusBadge } from '@shared/components/ui'
import { SwipeActions } from '@shared/components/ui/SwipeActions'
import type { EventStatus } from '@/types/event'

const STATUS_OPTIONS: { value: EventStatus | ''; label: string }[] = [
  { value: '', label: 'Tous statuts' },
  { value: 'planned', label: 'Planifié' },
  { value: 'risk', label: 'À risque' },
  { value: 'in_progress', label: 'En cours' },
  { value: 'incident', label: 'Incident' },
  { value: 'returned', label: 'Retourné' },
  { value: 'damage', label: 'Dommage' },
  { value: 'cancelled', label: 'Annulé' },
  { value: 'closed', label: 'Clôturé' },
]

export default function EvenementsListPage() {
  const navigate = useNavigate({ from: '/evenements/incidents' })
  const { page, q, status } = useSearch({ strict: false }) as { page: number; q: string; status: EventStatus | '' }

  const setPage   = (p: number) => navigate({ search: (prev) => ({ ...prev, page: p }) })
  const setSearch = (v: string) => navigate({ search: (prev) => ({ ...prev, q: v || undefined, page: 1 }) })
  const setStatus = (v: EventStatus | '') => navigate({ search: (prev) => ({ ...prev, status: v || undefined, page: 1 }) })

  const { data, isLoading, error: queryError, refetch } = useEvenementsList({
    skip: (page - 1) * 20,
    limit: 20,
    search: q || undefined,
    status: status || undefined,
  })

  const items = data?.items ?? []
  const totalPages = Math.ceil((data?.total ?? 0) / 20) ?? 1

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Événements terrain" />
        <button
          type="button"
          onClick={() => navigate({ to: '/reservations' as never })}
          className="btn-secondary text-sm"
        >
          Réservations
        </button>
      </div>

      {/* Filtres */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
          <input
            type="text"
            placeholder="Rechercher un événement…"
            value={q}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
          />
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as EventStatus | '')}
          className="input"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Desktop table */}
      <div className="hidden md:block card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-dark-600 text-dark-400 text-xs">
              <th className="text-left px-4 py-4 font-medium">Événement</th>
              <th className="text-left px-4 py-4 font-medium">Client</th>
              <th className="text-left px-4 py-4 font-medium">Date</th>
              <th className="text-left px-4 py-4 font-medium">Statut</th>
              <th className="text-left px-4 py-4 font-medium">Lieu</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} className="border-b border-dark-600 animate-pulse">
                  <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-28" /></td>
                  <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-36" /></td>
                  <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-24" /></td>
                  <td className="py-4 px-4"><div className="h-5 bg-dark-900 rounded w-16" /></td>
                  <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-20" /></td>
                  <td className="py-4 px-4"><div className="h-6 bg-dark-900 rounded w-6 ml-auto" /></td>
                </tr>
              ))
            ) : queryError ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <p className="text-red-400 mb-4">Erreur lors du chargement des événements.</p>
                  <button onClick={() => refetch()} className="btn-secondary text-sm">Réessayer</button>
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <p className="text-dark-400 mb-4">Aucun événement{q || status ? ' pour ces critères' : ''}.</p>
                  {!q && !status && (
                    <button
                      onClick={() => navigate({ to: '/reservations' as never })}
                      className="btn-secondary text-sm"
                    >
                      Voir les réservations
                    </button>
                  )}
                </td>
              </tr>
            ) : (
              items.map((ev) => (
                <tr
                  key={ev.id}
                  className="border-b border-dark-600/50 hover:bg-dark-600/30 cursor-pointer"
                  onClick={() => navigate({ to: '/evenements/$id/incidents', params: { id: String(ev.id) } })}
                >
                  <td className="px-4 py-4">
                    <p className="font-medium">{ev.name}</p>
                  </td>
                  <td className="px-4 py-4 text-dark-300">{ev.customer_name ?? '—'}</td>
                  <td className="px-4 py-4 text-dark-300">
                    {new Date(ev.event_date).toLocaleDateString('fr-FR')}
                  </td>
                  <td className="px-4 py-4">
                    <DomainStatusBadge status={ev.status} />
                  </td>
                  <td className="px-4 py-4 text-dark-400 text-xs">{ev.event_location ?? '—'}</td>
                  <td className="px-4 py-4">
                    {(ev.status === 'incident' || ev.status === 'risk') && (
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-4">
        {isLoading ? (
          <div className="space-y-4 animate-pulse">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="card p-4 space-y-2">
                <div className="flex justify-between">
                  <div className="h-3 skel rounded w-36" />
                  <div className="h-5 skel rounded w-16" />
                </div>
                <div className="h-2 skel rounded w-48" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="card text-center py-8 space-y-4">
            <p className="text-dark-400">Aucun événement{q || status ? ' pour ces critères' : ''}.</p>
            {!q && !status && (
              <button
                onClick={() => navigate({ to: '/reservations' as never })}
                className="btn-secondary text-sm"
              >
                Voir les réservations
              </button>
            )}
          </div>
        ) : (
          items.map((ev) => (
            <SwipeActions
              key={ev.id}
              actions={[]}
            >
              <div
                className="card cursor-pointer"
                onClick={() => navigate({ to: '/evenements/$id/incidents', params: { id: String(ev.id) } })}
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-medium">{ev.name}</p>
                    {ev.customer_name && <p className="text-dark-400 text-xs">{ev.customer_name}</p>}
                    <p className="text-dark-400 text-xs">
                      {new Date(ev.event_date).toLocaleDateString('fr-FR')}
                      {ev.event_location && ` · ${ev.event_location}`}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {(ev.status === 'incident' || ev.status === 'risk') && (
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                    )}
                    <DomainStatusBadge status={ev.status} />
                  </div>
                </div>
              </div>
            </SwipeActions>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="p-2 hover:bg-dark-600 rounded text-dark-400 disabled:opacity-40"
            aria-label="Page précédente"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="text-dark-400 text-sm">Page {page} / {totalPages}</span>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="p-2 hover:bg-dark-600 rounded text-dark-400 disabled:opacity-40"
            aria-label="Page suivante"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      )}
    </div>
  )
}
