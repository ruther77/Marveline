// Barre de progression sticky bottom — "14/16 complètes — 2 erreurs restantes"

import { useMemo } from 'react'
import type { LigneFactureRead } from '@/types/etl_import'
import { validateLigne } from '@/types/etl_import'

interface BottomProgressBarProps {
  lignes: LigneFactureRead[]
  showCelebration: boolean
}

export default function BottomProgressBar({ lignes, showCelebration }: BottomProgressBarProps) {
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
  const allComplete = stats.error === 0 && stats.warning === 0

  return (
    <div className={`sticky bottom-0 z-20 border-t transition-colors duration-300 ${
      showCelebration
        ? 'bg-emerald-50 border-emerald-300'
        : 'bg-white border-slate-200'
    }`}>
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex items-center gap-4">
          {/* Progress bar */}
          <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden flex">
            {pctValid > 0 && <div className="bg-green-500 transition-all duration-500" style={{ width: `${pctValid}%` }} />}
            {pctWarning > 0 && <div className="bg-amber-400 transition-all duration-500" style={{ width: `${pctWarning}%` }} />}
          </div>

          {/* Text */}
          <div className="text-sm shrink-0">
            {allComplete ? (
              <span className={`font-semibold ${showCelebration ? 'text-emerald-700' : 'text-green-600'}`}>
                {stats.total} lignes complètes — prêt à valider ✓
              </span>
            ) : (
              <span className="text-slate-600">
                <span className="font-semibold text-slate-800">{stats.valid}/{stats.total}</span> complètes
                {stats.error > 0 && <span className="text-red-500 ml-2">{stats.error} erreur{stats.error > 1 ? 's' : ''}</span>}
                {stats.warning > 0 && <span className="text-amber-500 ml-2">{stats.warning} à compléter</span>}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
