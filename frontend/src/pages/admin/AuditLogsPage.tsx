import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import { formatDate } from '@/lib/utils'
import { cn } from '@/lib/utils'
import {
  FileText,
  Search,
  ChevronLeft,
  ChevronRight,
  LogIn,
  LogOut,
  Shield,
  Edit,
  Plus,
  Trash2,
  Eye,
  X,
  Calendar,
} from 'lucide-react'

const actionIcons: Record<string, React.ElementType> = {
  CREATE: Plus,
  UPDATE: Edit,
  SOFT_DELETE: Trash2,
  HARD_DELETE: Trash2,
  READ_SENSITIVE: Eye,
  LOGIN_SUCCESS: LogIn,
  LOGIN_FAILED: Shield,
  LOGOUT: LogOut,
}

const actionColors: Record<string, string> = {
  CREATE: 'text-green-500 bg-green-500/10',
  UPDATE: 'text-blue-500 bg-blue-500/10',
  SOFT_DELETE: 'text-yellow-500 bg-yellow-500/10',
  HARD_DELETE: 'text-red-500 bg-red-500/10',
  READ_SENSITIVE: 'text-purple-500 bg-purple-500/10',
  LOGIN_SUCCESS: 'text-green-500 bg-green-500/10',
  LOGIN_FAILED: 'text-red-500 bg-red-500/10',
  LOGOUT: 'text-dark-400 bg-dark-700',
}

const actionLabels: Record<string, string> = {
  CREATE: 'Creation',
  UPDATE: 'Modification',
  SOFT_DELETE: 'Suppression',
  HARD_DELETE: 'Suppression definitive',
  READ_SENSITIVE: 'Lecture sensible',
  LOGIN_SUCCESS: 'Connexion',
  LOGIN_FAILED: 'Echec connexion',
  LOGOUT: 'Deconnexion',
}

export default function AuditLogsPage() {
  const [page, setPage] = useState(1)
  const [actionFilter, setActionFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')

  // Build filters object
  const filters: { action?: string; from_date?: string; to_date?: string } = {}
  if (actionFilter) filters.action = actionFilter
  if (fromDate) filters.from_date = `${fromDate}T00:00:00Z`
  if (toDate) filters.to_date = `${toDate}T23:59:59Z`

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', page, actionFilter, fromDate, toDate],
    queryFn: () =>
      adminApi.getAuditLogs(page, 50, Object.keys(filters).length > 0 ? filters : undefined),
  })

  const logs = data?.items || []
  const totalPages = data?.pages || 1

  // Client-side search filtering on description, entity_type, ip_address
  const filteredLogs = searchQuery.trim()
    ? logs.filter((log) => {
        const q = searchQuery.toLowerCase()
        return (
          (log.action || '').toLowerCase().includes(q) ||
          (log.entity_type || '').toLowerCase().includes(q) ||
          (log.description || '').toLowerCase().includes(q) ||
          (log.ip_address || '').toLowerCase().includes(q)
        )
      })
    : logs

  const hasActiveFilters = actionFilter || fromDate || toDate || searchQuery

  const clearFilters = () => {
    setActionFilter('')
    setSearchQuery('')
    setFromDate('')
    setToDate('')
    setPage(1)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Audit Logs</h1>
        <p className="text-dark-400 mt-1">
          Historique des actions sur la plateforme
        </p>
      </div>

      {/* Filters */}
      <div className="card space-y-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
            <input
              type="text"
              placeholder="Rechercher (action, entite, IP...)"
              className="input pl-10"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <select
            value={actionFilter}
            onChange={(e) => { setActionFilter(e.target.value); setPage(1) }}
            className="input w-full sm:w-48"
          >
            <option value="">Toutes les actions</option>
            <option value="CREATE">Creation</option>
            <option value="UPDATE">Modification</option>
            <option value="SOFT_DELETE">Suppression</option>
            <option value="READ_SENSITIVE">Lecture sensible</option>
            <option value="LOGIN_SUCCESS">Connexion</option>
            <option value="LOGIN_FAILED">Echec connexion</option>
            <option value="LOGOUT">Deconnexion</option>
          </select>
        </div>

        {/* Date range filters */}
        <div className="flex flex-col sm:flex-row gap-4 items-end">
          <div className="flex-1">
            <label className="text-sm text-dark-400 mb-1 block">Date debut</label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
              <input
                type="date"
                value={fromDate}
                onChange={(e) => { setFromDate(e.target.value); setPage(1) }}
                className="input pl-10"
              />
            </div>
          </div>
          <div className="flex-1">
            <label className="text-sm text-dark-400 mb-1 block">Date fin</label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
              <input
                type="date"
                value={toDate}
                onChange={(e) => { setToDate(e.target.value); setPage(1) }}
                className="input pl-10"
              />
            </div>
          </div>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="btn-ghost text-sm flex items-center gap-1.5 text-dark-400 hover:text-white"
            >
              <X className="w-4 h-4" />
              Reinitialiser
            </button>
          )}
        </div>
      </div>

      {/* Logs Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Action
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Entite
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Description
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  IP
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Date
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-dark-400">
                    Chargement...
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-dark-400">
                    Aucun log trouve
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => {
                  const Icon = actionIcons[log.action] || FileText
                  const colorClass =
                    actionColors[log.action] || 'text-dark-400 bg-dark-700'

                  return (
                    <tr
                      key={log.id}
                      className="border-b border-dark-700/50 hover:bg-dark-700/30"
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div
                            className={cn(
                              'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                              colorClass
                            )}
                          >
                            <Icon className="w-4 h-4" />
                          </div>
                          <span className="font-medium text-sm">
                            {actionLabels[log.action] || log.action}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-dark-400">
                          {log.entity_type}
                          {log.entity_id != null && ` #${log.entity_id}`}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-dark-300 max-w-xs truncate block">
                          {log.description || '-'}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm font-mono text-dark-400">
                          {log.ip_address}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm text-dark-400 whitespace-nowrap">
                        {formatDate(log.created_at)}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-dark-700">
            <p className="text-sm text-dark-400">
              Page {page} sur {totalPages}
              {data?.total != null && ` (${data.total} resultats)`}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-ghost p-2 disabled:opacity-50"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn-ghost p-2 disabled:opacity-50"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
