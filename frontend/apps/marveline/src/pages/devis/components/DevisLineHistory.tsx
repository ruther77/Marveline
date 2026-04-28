import { History, Plus, Pencil, Trash2, Loader2 } from 'lucide-react'
import { useDevisLineHistory } from '@/api/queries/useDevis'
import type { DevisLineHistoryEntry } from '@/types/devis'

interface DevisLineHistoryProps {
  devisId: number
  className?: string
}

const ACTION_CONFIG = {
  create: { icon: Plus, label: 'Ajout', color: 'text-green-400', bg: 'bg-green-400/10' },
  update: { icon: Pencil, label: 'Modification', color: 'text-blue-400', bg: 'bg-blue-400/10' },
  delete: { icon: Trash2, label: 'Suppression', color: 'text-red-400', bg: 'bg-red-400/10' },
} as const

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

function DiffLine({ field, oldVal, newVal }: { field: string; oldVal: unknown; newVal: unknown }) {
  if (oldVal === newVal) return null
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-dark-400 w-28 shrink-0">{field}</span>
      {oldVal !== undefined && oldVal !== null && (
        <span className="text-red-400 line-through">{String(oldVal)}</span>
      )}
      {newVal !== undefined && newVal !== null && (
        <span className="text-green-400">{String(newVal)}</span>
      )}
    </div>
  )
}

/**
 * G28 — Historique des modifications ligne par ligne d'un devis.
 * Affiche une timeline avec diff pour chaque changement.
 */
export default function DevisLineHistory({ devisId, className = '' }: DevisLineHistoryProps) {
  const { data, isLoading } = useDevisLineHistory(devisId)

  if (isLoading) {
    return (
      <div className={`space-y-3 ${className}`}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-16 bg-dark-800 rounded-lg animate-pulse" />
        ))}
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className={`text-center py-8 ${className}`}>
        <History className="w-8 h-8 text-dark-500 mx-auto mb-2" />
        <p className="text-dark-400 text-sm">Aucune modification enregistree.</p>
      </div>
    )
  }

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        <History className="w-4 h-4 text-dark-400" />
        <span className="text-sm font-medium text-dark-300">
          Historique des lignes ({data.length})
        </span>
      </div>

      {data.map((entry) => {
        const config = ACTION_CONFIG[entry.action] || ACTION_CONFIG.update
        const Icon = config.icon
        const fields = new Set([
          ...Object.keys(entry.old_values || {}),
          ...Object.keys(entry.new_values || {}),
        ])

        const label = entry.new_values?.label || entry.old_values?.label || `Ligne #${entry.devis_line_id || '?'}`

        return (
          <div key={entry.id} className="card rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center ${config.bg}`}>
                <Icon className={`w-3 h-3 ${config.color}`} />
              </div>
              <span className={`text-xs font-semibold uppercase ${config.color}`}>
                {config.label}
              </span>
              <span className="text-xs text-dark-500 truncate flex-1">{label}</span>
              <span className="text-xs text-dark-500 shrink-0">{formatDate(entry.created_at)}</span>
            </div>

            {entry.action !== 'create' && entry.old_values && entry.new_values && (
              <div className="space-y-0.5 ml-8">
                {Array.from(fields)
                  .filter((f) => f !== 'label')
                  .map((field) => (
                    <DiffLine
                      key={field}
                      field={field}
                      oldVal={(entry.old_values as Record<string, unknown>)?.[field]}
                      newVal={(entry.new_values as Record<string, unknown>)?.[field]}
                    />
                  ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
