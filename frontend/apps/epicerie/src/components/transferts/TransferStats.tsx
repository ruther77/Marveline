// Stats mensuelles transferts

import { useMemo } from 'react'
import { formatCents } from '@/utils/etl-helpers'
import type { InternalTransferRead } from '@/types/epicerie-v2'

export default function TransferStats({ transfers }: { transfers: InternalTransferRead[] }) {
  const stats = useMemo(() => {
    const now = new Date()
    const month = now.getMonth()
    const year = now.getFullYear()

    let count = 0
    let articles = 0
    let htCts = 0
    for (const t of transfers) {
      const d = new Date(t.created_at)
      if (d.getMonth() === month && d.getFullYear() === year) {
        count++
        articles += t.lignes.length
        htCts += t.lignes.reduce((sum, line) => sum + line.montant_ht, 0)
      }
    }
    return { count, articles, htCts }
  }, [transfers])

  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-slate-400">Ce mois</p>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-500">
        <span className="font-semibold text-slate-800">
          {stats.count} transfert{stats.count > 1 ? 's' : ''}
        </span>
        <span className="text-slate-300">·</span>
        <span>{stats.articles} articles</span>
        <span className="text-slate-300">·</span>
        <span className="font-mono text-slate-700">{formatCents(stats.htCts)} HT</span>
      </div>
    </div>
  )
}
