import { useState } from 'react'
import { useParams } from '@tanstack/react-router'
import { History, ArrowLeft } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { useInvoiceAudit, useInvoiceFull } from '@/api/queries'
import { cn } from '@/lib/utils'

const ACTION_COLORS: Record<string, string> = {
  CREATE: 'bg-green-900/40 text-green-300 border-green-700/40',
  UPDATE: 'bg-blue-900/40 text-blue-300 border-blue-700/40',
  DELETE: 'bg-red-900/40 text-red-300 border-red-700/40',
  CANCEL: 'bg-orange-900/40 text-orange-300 border-orange-700/40',
  PAYMENT: 'bg-purple-900/40 text-purple-300 border-purple-700/40',
  SENT: 'bg-sky-900/40 text-sky-300 border-sky-700/40',
}

const FILTER_PILLS: { value: string; label: string }[] = [
  { value: 'all', label: 'Tous' },
  { value: 'SENT', label: 'Envoi' },
  { value: 'PAYMENT', label: 'Paiements' },
  { value: 'CANCEL', label: 'Annulations' },
  { value: 'UPDATE', label: 'Modifications' },
  { value: 'CREATE', label: 'Créations' },
]

function formatDate(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
}

export default function InvoiceAuditPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const invoiceId = id ? parseInt(id, 10) : null
  const [activeFilter, setActiveFilter] = useState('all')

  const { data: invoice } = useInvoiceFull(invoiceId)
  const { data: logs = [], isLoading } = useInvoiceAudit(invoiceId)
  const filteredLogs = activeFilter === 'all' ? logs : logs.filter((l) => l.action === activeFilter)

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-4">
        <Link to="/finance/invoices" aria-label="Retour aux factures" className="p-2 hover:bg-dark-600 rounded text-dark-400">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <History className="w-5 h-5 text-gold-400" />
        <h1 className="text-xl font-semibold">
          Audit — {invoice?.invoice_number ?? `Facture #${invoiceId}`}
        </h1>
      </div>

      {/* Filter pills */}
      <div className="overflow-x-auto -mx-4 px-4">
        <div className="flex gap-2 pb-1 min-w-max">
          {FILTER_PILLS.map((pill) => {
            const count = pill.value === 'all' ? logs.length : logs.filter((l) => l.action === pill.value).length
            if (pill.value !== 'all' && count === 0) return null
            return (
              <button
                key={pill.value}
                type="button"
                onClick={() => setActiveFilter(pill.value)}
                className={cn(
                  'px-4 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors',
                  activeFilter === pill.value
                    ? 'bg-primary-500 text-white'
                    : 'bg-dark-900 text-dark-300 hover:bg-dark-600 hover:text-dark-50'
                )}
              >
                {pill.label} {count > 0 && <span className="ml-1 opacity-70">({count})</span>}
              </button>
            )
          })}
        </div>
      </div>

      {isLoading ? (
        <div className="card divide-y divide-dark-600 animate-pulse">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-start gap-4 p-4">
              <div className="w-2 h-2 mt-2 rounded-full skel shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-48" />
                <div className="h-2 skel rounded w-64" />
              </div>
              <div className="h-2 skel rounded w-24 shrink-0" />
            </div>
          ))}
        </div>
      ) : filteredLogs.length === 0 ? (
        <div className="card text-center py-14">
          <History className="w-10 h-10 text-dark-500 mx-auto mb-4" />
          <p className="font-medium">
            {activeFilter === 'all' ? "Aucun événement d'audit" : 'Aucun événement pour ce filtre'}
          </p>
          <p className="text-dark-400 text-sm mt-1">
            {activeFilter === 'all'
              ? "Cette facture n'a pas encore d'historique."
              : 'Essayez un autre filtre ou sélectionnez "Tous".'}
          </p>
        </div>
      ) : (
        <div className="card divide-y divide-dark-600">
          {filteredLogs.map((log) => (
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
