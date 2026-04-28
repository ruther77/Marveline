// Carte transfert compacte — liste

import { Link } from '@tanstack/react-router'
import { CheckCircle2, Clock, XCircle } from 'lucide-react'
import { formatCents, formatDateTime } from '@/utils/etl-helpers'
import { getTransferDisplayTtcCts } from '@/utils/transferts'
import type { InternalTransferRead, TransferStatus } from '@/types/epicerie-v2'

const STATUS: Record<TransferStatus, { label: string; cls: string; icon: typeof Clock }> = {
  PENDING:   { label: 'En attente', cls: 'text-amber-600 bg-amber-50', icon: Clock },
  VALIDATED: { label: 'Validé',     cls: 'text-emerald-600 bg-emerald-50', icon: CheckCircle2 },
  CANCELLED: { label: 'Annulé',     cls: 'text-slate-400 bg-slate-50', icon: XCircle },
}

interface TransferCardProps {
  transfer: InternalTransferRead
  onQuickValidate?: (transfer: InternalTransferRead) => void
  isValidating?: boolean
}

export default function TransferCard({ transfer: t, onQuickValidate, isValidating }: TransferCardProps) {
  const cfg = STATUS[t.status]
  const Icon = cfg.icon
  const isPending = t.status === 'PENDING'
  const totalTtcCts = getTransferDisplayTtcCts(t)

  return (
    <Link
      to="/transferts/$id" params={{ id: String(t.id) }}
      className={`block rounded-xl border p-4 transition-all hover:shadow-md ${
        isPending ? 'border-amber-200 bg-amber-50/20' : 'border-slate-200 bg-white'
      }`}
    >
      <div className="flex gap-4">
        <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${
          isPending ? 'bg-amber-500' : t.status === 'VALIDATED' ? 'bg-emerald-500' : 'bg-slate-300'
        }`} />

        <div className="flex-1 min-w-0">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="mb-0.5 flex items-center gap-2">
                <span className="truncate text-sm font-semibold text-slate-800">
                  {t.reference || `TRF-${t.id}`}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                <span>{formatDateTime(t.created_at)}</span>
                <span>{t.lignes.length} article{t.lignes.length > 1 ? 's' : ''}</span>
                <span className="font-mono">{formatCents(totalTtcCts)} TTC</span>
              </div>
            </div>

            {isPending && onQuickValidate ? (
              <button
                type="button"
                onClick={event => {
                  event.preventDefault()
                  event.stopPropagation()
                  onQuickValidate(t)
                }}
                disabled={isValidating}
                className="inline-flex min-h-11 items-center justify-center rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
              >
                {isValidating ? 'Validation…' : 'Valider ✓'}
              </button>
            ) : (
              <span className={`inline-flex items-center gap-1 self-start rounded px-2 py-1 text-[11px] font-medium ${cfg.cls}`}>
                <Icon className="h-3 w-3" />
                {cfg.label}
              </span>
            )}
          </div>
        </div>
      </div>
    </Link>
  )
}
