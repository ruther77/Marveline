// Résumé totaux transfert — HT / TVA / TTC

import { formatCents } from '@/utils/etl-helpers'
import { getTransferTvaCts, getTransferTtcCts } from '@/utils/transferts'

interface TransferSummaryProps {
  totalHtCts: number
  totalTtcCts?: number
  totalTvaCts?: number
  tvaPct?: number // centièmes, défaut 2000 = 20%
}

export default function TransferSummary({
  totalHtCts,
  totalTtcCts,
  totalTvaCts,
  tvaPct = 2000,
}: TransferSummaryProps) {
  const tvaCts = totalTvaCts ?? getTransferTvaCts(totalHtCts, totalTtcCts, tvaPct)
  const ttcCts = totalTtcCts ?? (totalHtCts + tvaCts)

  return (
    <div className="border-t border-slate-200 bg-slate-50 px-4 py-3">
      <div className="flex flex-col items-end gap-1 text-sm">
        <div className="flex gap-8">
          <span className="text-slate-500">Total HT</span>
          <span className="font-mono text-slate-700 w-24 text-right">{formatCents(totalHtCts)}</span>
        </div>
        <div className="flex gap-8">
          <span className="text-slate-500">TVA {(tvaPct / 100).toFixed(0)}%</span>
          <span className="font-mono text-slate-400 w-24 text-right">{formatCents(tvaCts)}</span>
        </div>
        <div className="flex gap-8 pt-1 border-t border-slate-300">
          <span className="font-semibold text-slate-700">Total TTC</span>
          <span className="font-mono font-bold text-slate-900 w-24 text-right">{formatCents(ttcCts)}</span>
        </div>
      </div>
    </div>
  )
}
