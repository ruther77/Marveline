import { formatDistanceToNow, parseISO } from 'date-fns'
import { fr } from 'date-fns/locale'
import { cn } from '../../lib/utils'

export interface TimelineEntry {
  date: string
  user: string
  action: string
  detail?: string
  type: 'state' | 'action' | 'note'
}

interface TimelineAuditProps {
  entries: TimelineEntry[]
  className?: string
}

const typeConfig = {
  state: { dot: 'bg-blue-500', icon: '⟳' },
  action: { dot: 'bg-green-500', icon: '✓' },
  note: { dot: 'bg-yellow-500', icon: '✎' },
}

function tryRelative(date: string): string {
  try {
    return formatDistanceToNow(parseISO(date), { addSuffix: true, locale: fr })
  } catch {
    return date
  }
}

export function TimelineAudit({ entries, className }: TimelineAuditProps) {
  const sorted = [...entries].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
  )

  if (sorted.length === 0) {
    return (
      <p className="text-sm text-dark-400 py-4 text-center">Aucun historique disponible</p>
    )
  }

  return (
    <div className={cn('space-y-0', className)}>
      {sorted.map((entry, i) => {
        const cfg = typeConfig[entry.type]
        return (
          <div key={i} className="flex gap-4">
            {/* Ligne verticale + dot */}
            <div className="flex flex-col items-center">
              <div className={cn('w-2.5 h-2.5 rounded-full mt-1.5 shrink-0', cfg.dot)} />
              {i < sorted.length - 1 && <div className="w-px flex-1 bg-dark-600 mt-1" />}
            </div>
            {/* Contenu */}
            <div className="pb-4 flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium">{entry.action}</span>
                <span className="text-xs text-dark-400">{tryRelative(entry.date)}</span>
              </div>
              <p className="text-xs text-dark-300 mt-0.5">par {entry.user}</p>
              {entry.detail && (
                <p className="text-xs text-dark-400 mt-1 bg-dark-900 rounded px-2 py-1">
                  {entry.detail}
                </p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
