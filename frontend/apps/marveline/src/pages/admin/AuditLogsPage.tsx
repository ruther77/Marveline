import { useState } from 'react'
import { PageHeader } from '@/components/PageHeader'
import { useAuditLogs } from '@/api/queries'
import { formatDate } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { useHasScope } from '@/hooks/useHasScope'
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
  LOGOUT: 'text-dark-400 bg-dark-900',
}

const actionLabels: Record<string, string> = {
  CREATE: 'Création',
  UPDATE: 'Modification',
  SOFT_DELETE: 'Suppression',
  HARD_DELETE: 'Suppression définitive',
  READ_SENSITIVE: 'Lecture sensible',
  LOGIN_SUCCESS: 'Connexion',
  LOGIN_FAILED: 'Échec connexion',
  LOGOUT: 'Déconnexion',
  USER_UPDATED: 'Utilisateur modifié',
  PASSWORD_CHANGED: 'Mot de passe changé',
  MFA_ENABLED: 'MFA activé',
  MFA_DISABLED: 'MFA désactivé',
}

const entityLabels: Record<string, string> = {
  User: 'Utilisateur',
  Customer: 'Client',
  Invoice: 'Facture',
  Product: 'Produit',
  Reservation: 'Réservation',
  Devis: 'Devis',
  Vente: 'Vente',
  Bundle: 'Formule',
  Category: 'Catégorie',
  Deposit: 'Acompte',
  Audit: 'Audit',
  Session: 'Session',
  ApiKey: 'Clé API',
  FeatureFlag: 'Feature flag',
  InventoryMovement: 'Mouvement stock',
  SupplierOrder: 'Commande fournisseur',
  Payment: 'Paiement',
  CreditNote: 'Avoir',
  Notification: 'Notification',
}

const fieldLabels: Record<string, string> = {
  email: 'e-mail',
  first_name: 'prénom',
  last_name: 'nom',
  role: 'rôle',
  is_active: 'statut actif',
  phone: 'téléphone',
  company: 'entreprise',
  address: 'adresse',
  notes: 'notes',
  status: 'statut',
  name: 'nom',
  price_cents: 'prix',
  quantity: 'quantité',
  description: 'description',
  category: 'catégorie',
  due_date: 'échéance',
  reference: 'référence',
}

function translateDescription(desc: string | null | undefined, action: string, entityType: string | null, entityId: number | null): string {
  if (!desc) return '-'

  // "Accessed sensitive data Customer #None" / "Accessed sensitive data User #1"
  const sensMatch = desc.match(/^Accessed sensitive data (\w+)\s*#?(.*)$/)
  if (sensMatch) {
    const entity = entityLabels[sensMatch[1]] || sensMatch[1]
    const id = sensMatch[2] && sensMatch[2] !== 'None' ? ` #${sensMatch[2]}` : ''
    return `Consultation des données ${entity}${id}`
  }

  // "Listed sensitive data Customer"
  const listMatch = desc.match(/^Listed sensitive data (\w+)$/)
  if (listMatch) {
    const entity = entityLabels[listMatch[1]] || listMatch[1]
    return `Consultation de la liste ${entity}`
  }

  // "User admin@carocorp.dev updated: ['email', 'first_name']"
  const updateMatch = desc.match(/^User .+ updated: \[(.+)\]$/)
  if (updateMatch) {
    const fields = updateMatch[1]
      .replace(/'/g, '')
      .split(',')
      .map((f) => f.trim())
      .map((f) => fieldLabels[f] || f)
      .join(', ')
    return `Champs modifiés : ${fields}`
  }

  // "PATCH /api/v1/users/1" or "POST /api/v1/ventes" — method + path
  const httpMatch = desc.match(/^(GET|POST|PUT|PATCH|DELETE)\s+\/api\/v1\/(.+)$/)
  if (httpMatch) {
    const method = httpMatch[1]
    const methodLabels: Record<string, string> = {
      GET: 'Lecture',
      POST: 'Création',
      PUT: 'Mise à jour',
      PATCH: 'Modification',
      DELETE: 'Suppression',
    }
    const entity = entityLabels[entityType || ''] || entityType || httpMatch[2]
    const id = entityId != null ? ` #${entityId}` : ''
    return `${methodLabels[method] || method} ${entity}${id}`
  }

  return desc
}

export default function AuditLogsPage() {
  const canReadAudit = useHasScope('audit:read')
  const [page, setPage] = useState(1)
  const [actionFilter, setActionFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')

  const { data, isLoading } = useAuditLogs({
    skip: (page - 1) * 50,
    limit: 50,
    action: actionFilter || undefined,
    from_date: fromDate ? `${fromDate}T00:00:00Z` : undefined,
    to_date: toDate ? `${toDate}T23:59:59Z` : undefined,
  })

  const logs = data?.items || []
  const totalPages = Math.ceil((data?.total ?? 0) / 50) || 1

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

  if (!canReadAudit) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <Shield className="w-12 h-12 text-dark-600 mb-4" />
        <h2 className="text-lg font-semibold text-dark-300">Accès restreint</h2>
        <p className="text-sm text-dark-500 mt-2">
          Vous n'avez pas les droits pour consulter les journaux d'audit.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Journal d'audit" subtitle="Historique des actions sur la plateforme" />

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
              className="btn-ghost text-sm flex items-center gap-1.5 text-dark-400 hover:text-dark-50"
            >
              <X className="w-4 h-4" />
              Reinitialiser
            </button>
          )}
        </div>
      </div>

      {/* Logs */}
      <div className="card p-0 overflow-hidden">
        {/* Vue mobile */}
        <div className="sm:hidden">
          {isLoading ? (
            <div className="animate-pulse divide-y divide-dark-600">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex items-start gap-4 px-4 py-4">
                  <div className="w-7 h-7 rounded-lg skel shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 skel rounded w-40" />
                    <div className="h-2 skel rounded w-56" />
                  </div>
                </div>
              ))}
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="py-8 text-center text-dark-400">Aucun log trouve</div>
          ) : (
            filteredLogs.map((log) => {
              const Icon = actionIcons[log.action] || FileText
              const colorClass = actionColors[log.action] || 'text-dark-400 bg-dark-900'
              return (
                <div
                  key={log.id}
                  className="flex items-start gap-4 px-4 py-4 border-b border-dark-600 last:border-0"
                >
                  <div
                    className={cn(
                      'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5',
                      colorClass
                    )}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium">
                        {actionLabels[log.action] || log.action}
                      </span>
                      <span className="text-xs text-dark-400">
                        {entityLabels[log.entity_type] || log.entity_type}
                        {log.entity_id != null && ` #${log.entity_id}`}
                      </span>
                    </div>
                    {log.description && (
                      <p className="text-xs text-dark-400 mt-0.5 line-clamp-2">{translateDescription(log.description, log.action, log.entity_type, log.entity_id)}</p>
                    )}
                    <div className="text-xs text-dark-500 mt-0.5">
                      {log.ip_address && <span className="font-mono mr-2">{log.ip_address}</span>}
                      {formatDate(log.created_at)}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* Vue desktop */}
        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-600">
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">
                  Action
                </th>
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">
                  Entite
                </th>
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">
                  Description
                </th>
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">
                  IP
                </th>
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">
                  Date
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="border-b border-dark-600 animate-pulse">
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-28" /></td>
                    <td className="py-4 px-4"><div className="h-5 bg-dark-900 rounded w-20" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-32" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-40" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-24" /></td>
                  </tr>
                ))
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
                    actionColors[log.action] || 'text-dark-400 bg-dark-900'

                  return (
                    <tr
                      key={log.id}
                      className="border-b border-dark-600/50 hover:bg-dark-600/30"
                    >
                      <td className="py-4 px-4">
                        <div className="flex items-center gap-4">
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
                      <td className="py-4 px-4">
                        <span className="text-sm text-dark-400">
                          {entityLabels[log.entity_type] || log.entity_type}
                          {log.entity_id != null && ` #${log.entity_id}`}
                        </span>
                      </td>
                      <td className="py-4 px-4">
                        <span className="text-sm text-dark-300 max-w-xs truncate block">
                          {translateDescription(log.description, log.action, log.entity_type, log.entity_id)}
                        </span>
                      </td>
                      <td className="py-4 px-4">
                        <span className="text-sm font-mono text-dark-400">
                          {log.ip_address}
                        </span>
                      </td>
                      <td className="py-4 px-4 text-sm text-dark-400 whitespace-nowrap">
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
          <div className="flex items-center justify-between px-4 py-4 border-t border-dark-600">
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
