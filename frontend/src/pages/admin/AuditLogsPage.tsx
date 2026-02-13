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
  Key,
  User,
  AlertTriangle,
} from 'lucide-react'

const actionIcons: Record<string, React.ElementType> = {
  login: LogIn,
  logout: LogOut,
  mfa_enable: Shield,
  mfa_disable: Shield,
  password_change: Key,
  user_update: User,
  session_terminate: AlertTriangle,
}

const actionColors: Record<string, string> = {
  login: 'text-green-500 bg-green-500/10',
  logout: 'text-blue-500 bg-blue-500/10',
  mfa_enable: 'text-green-500 bg-green-500/10',
  mfa_disable: 'text-yellow-500 bg-yellow-500/10',
  password_change: 'text-purple-500 bg-purple-500/10',
  session_terminate: 'text-red-500 bg-red-500/10',
}

export default function AuditLogsPage() {
  const [page, setPage] = useState(1)
  const [actionFilter, setActionFilter] = useState<string>('')

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', page, actionFilter],
    queryFn: () =>
      adminApi.getAuditLogs(page, 50, actionFilter ? { action: actionFilter } : undefined),
  })

  const logs = data?.items || []
  const totalPages = data?.pages || 1

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Audit Logs</h1>
        <p className="text-dark-400 mt-1">
          Historique des actions de sécurité sur la plateforme
        </p>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
            <input
              type="text"
              placeholder="Rechercher..."
              className="input pl-10"
            />
          </div>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="input w-full sm:w-48"
          >
            <option value="">Toutes les actions</option>
            <option value="login">Connexion</option>
            <option value="logout">Déconnexion</option>
            <option value="mfa_enable">2FA activé</option>
            <option value="mfa_disable">2FA désactivé</option>
            <option value="password_change">Changement mot de passe</option>
            <option value="session_terminate">Session terminée</option>
          </select>
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
                  Ressource
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
                  <td colSpan={4} className="py-8 text-center text-dark-400">
                    Chargement...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-dark-400">
                    Aucun log trouvé
                  </td>
                </tr>
              ) : (
                logs.map((log) => {
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
                              'w-8 h-8 rounded-lg flex items-center justify-center',
                              colorClass
                            )}
                          >
                            <Icon className="w-4 h-4" />
                          </div>
                          <span className="font-medium capitalize">
                            {log.action.replace(/_/g, ' ')}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-dark-400">
                          {log.resource} {log.resource_id && `#${log.resource_id}`}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm font-mono text-dark-400">
                          {log.ip_address}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm text-dark-400">
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
