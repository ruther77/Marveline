// Compteurs mensuels header — "Ce mois : X factures · Y lignes · Z€ HT"

import { useMemo } from 'react'
import type { EtlImportRead } from '@/types/etl_import'
import { formatCents } from '@/utils/etl-helpers'

interface MonthlyStatsProps {
  imports: EtlImportRead[]
}

export default function MonthlyStats({ imports }: MonthlyStatsProps) {
  const stats = useMemo(() => {
    const now = new Date()
    const month = now.getMonth()
    const year = now.getFullYear()

    let factures = 0
    let lignes = 0
    let htCts = 0

    for (const imp of imports) {
      const d = new Date(imp.created_at)
      if (d.getMonth() === month && d.getFullYear() === year) {
        factures++
        lignes += imp.nb_lignes_total ?? 0
        htCts += imp.montant_ht_total ?? 0
      }
    }

    return { factures, lignes, htCts }
  }, [imports])

  if (stats.factures === 0) return null

  return (
    <div className="flex items-center gap-2 text-xs text-slate-500">
      <span className="font-medium text-slate-700">Ce mois :</span>
      <span>{stats.factures} facture{stats.factures > 1 ? 's' : ''}</span>
      <span className="text-slate-300">·</span>
      <span>{stats.lignes} lignes</span>
      <span className="text-slate-300">·</span>
      <span className="font-mono">{formatCents(stats.htCts)} HT</span>
    </div>
  )
}
