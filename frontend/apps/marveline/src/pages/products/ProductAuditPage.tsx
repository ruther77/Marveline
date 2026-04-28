import { useParams } from '@tanstack/react-router'
import { History } from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import { useProductAudit, useProductDetail } from '@/api/queries'
import { ErrorState } from '@shared/components/ui/EmptyState'

const ACTION_COLORS: Record<string, string> = {
  CREATE: 'bg-green-900/40 text-green-300 border-green-700/40',
  UPDATE: 'bg-blue-900/40 text-blue-300 border-blue-700/40',
  DELETE: 'bg-red-900/40 text-red-300 border-red-700/40',
  SOFT_DELETE: 'bg-orange-900/40 text-orange-300 border-orange-700/40',
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
}

export default function ProductAuditPage() {
  const { id: rawId } = useParams({ strict: false }) as { id: string }
  const id = parseInt(rawId, 10)

  const { data: product } = useProductDetail(isNaN(id) ? null : id)
  const { data: logs, isLoading, error, refetch } = useProductAudit(isNaN(id) ? null : id)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <BackButton />
        <History className="w-5 h-5 text-gold-400" />
        <h1 className="text-xl font-semibold">
          Audit — {product?.name ?? `Produit #${id}`}
        </h1>
      </div>

      {isLoading ? (
        <div className="card divide-y divide-dark-600 animate-pulse">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-start gap-4 p-4">
              <div className="w-2 h-2 mt-2 rounded-full skel shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-48" />
                <div className="h-2 skel rounded w-32" />
              </div>
              <div className="h-2 skel rounded w-24 shrink-0" />
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : !logs || logs.length === 0 ? (
        <div className="card text-center py-14">
          <History className="w-10 h-10 text-dark-500 mx-auto mb-4" />
          <p className="font-medium">Aucun événement d'audit</p>
          <p className="text-dark-400 text-sm mt-1">Ce produit n'a pas encore d'historique.</p>
        </div>
      ) : (
        <div className="card divide-y divide-dark-600">
          {logs.map((log) => (
            <div key={log.id} className="px-4 py-4 flex items-start gap-4">
              <div className="shrink-0 pt-0.5">
                <span
                  className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                    ACTION_COLORS[log.action] ?? 'bg-dark-900 text-dark-300 border-dark-600'
                  }`}
                >
                  {log.action}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm">{log.description ?? log.action}</p>
                {log.changes && (
                  <div className="mt-1 space-y-0.5">
                    {/* Format snapshot CREATE: {after: {...}} */}
                    {!!(log.changes.after && typeof log.changes.after === 'object' && !log.changes.before) && (
                      <p className="text-dark-400 text-xs">
                        {Object.entries(log.changes.after as Record<string, unknown>)
                          .filter(([, v]) => v !== null && v !== undefined)
                          .slice(0, 5)
                          .map(([k, v]) => `${k}: ${String(v)}`)
                          .join(' · ')}
                      </p>
                    )}
                    {/* Format snapshot DELETE: {before: {...}} */}
                    {!!(log.changes.before && typeof log.changes.before === 'object' && !log.changes.after) && (
                      <p className="text-dark-400 text-xs">
                        {Object.entries(log.changes.before as Record<string, unknown>)
                          .filter(([, v]) => v !== null && v !== undefined)
                          .slice(0, 5)
                          .map(([k, v]) => `${k}: ${String(v)}`)
                          .join(' · ')}
                      </p>
                    )}
                    {/* Format UPDATE: {field: {before, after}} */}
                    {Object.entries(log.changes).map(([field, val]) => {
                      if (field === 'before' || field === 'after') return null
                      const change = val as { before?: unknown; after?: unknown }
                      if (change?.before !== undefined && change?.after !== undefined) {
                        return (
                          <p key={field} className="text-dark-400 text-xs">
                            <span className="text-dark-300">{field}</span>:{' '}
                            <span className="text-red-400 line-through">{String(change.before)}</span>
                            {' → '}
                            <span className="text-green-400">{String(change.after)}</span>
                          </p>
                        )
                      }
                      return null
                    })}
                  </div>
                )}
              </div>
              <span className="text-dark-400 text-xs shrink-0">{formatDate(log.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
