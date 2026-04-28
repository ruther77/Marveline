import { formatDate, formatCents } from '@/lib/utils'
import type { DevisNegotiationEntry } from '@/types/devis'

interface DevisNegotiationSummaryProps {
  entries: DevisNegotiationEntry[]
  devisId: number
  onViewAll: () => void
}

export function DevisNegotiationSummary({ entries, onViewAll }: DevisNegotiationSummaryProps) {
  if (!entries?.length) return null

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-medium">Négociation ({entries.length})</h2>
        <button
          onClick={onViewAll}
          className="text-sm text-gold-400 hover:text-gold-300"
        >
          Voir tout →
        </button>
      </div>
      <div className="space-y-2">
        {entries.slice(-3).map((entry) => (
          <div key={entry.id} className="text-sm">
            <span className="text-dark-400">{entry.author} · {formatDate(entry.created_at)}</span>
            <p className="mt-0.5">{entry.message}</p>
            {entry.proposed_amount_cents !== undefined && (
              <p className="text-gold-400 text-xs mt-0.5">
                Proposition : {formatCents(entry.proposed_amount_cents)}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
