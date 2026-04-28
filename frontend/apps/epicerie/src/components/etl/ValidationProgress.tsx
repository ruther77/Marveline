// Barre de progression validation — valid/warning/error

import { useMemo } from 'react'
import type { LigneFactureRead } from '@/types/etl_import'
import { validateLigne } from '@/types/etl_import'

export default function ValidationProgress({ lignes }: { lignes: LigneFactureRead[] }) {
  const stats = useMemo(() => {
    let valid = 0, warning = 0, error = 0
    for (const l of lignes) {
      const v = validateLigne(l)
      if (v.status === 'valid') valid++
      else if (v.status === 'warning') warning++
      else error++
    }
    return { valid, warning, error, total: lignes.length }
  }, [lignes])

  if (stats.total === 0) return null

  const pctValid = (stats.valid / stats.total) * 100
  const pctWarning = (stats.warning / stats.total) * 100
  const pctError = (stats.error / stats.total) * 100

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-slate-700">Qualité des lignes</span>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            {stats.valid} complètes
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            {stats.warning} à compléter
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            {stats.error} à corriger
          </span>
        </div>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden flex">
        {pctValid > 0 && <div className="bg-green-500 transition-all duration-300" style={{ width: `${pctValid}%` }} />}
        {pctWarning > 0 && <div className="bg-amber-400 transition-all duration-300" style={{ width: `${pctWarning}%` }} />}
        {pctError > 0 && <div className="bg-red-500 transition-all duration-300" style={{ width: `${pctError}%` }} />}
      </div>
      {(stats.warning > 0 || stats.error > 0) && (
        <p className="text-xs text-slate-400 mt-2">
          {stats.error > 0 && <span className="text-red-500">Cliquez sur les champs en rouge pour saisir les données manquantes. </span>}
          {stats.warning > 0 && <span className="text-amber-500">Les champs en orange sont optionnels mais améliorent la qualité.</span>}
        </p>
      )}
    </div>
  )
}
