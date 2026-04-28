// Barre de réconciliation — montants déclarés vs calculés

import type { EtlImportDetail } from '@/types/etl_import'
import { formatCents } from '@/utils/etl-helpers'

export default function ReconciliationBar({ detail }: { detail: EtlImportDetail }) {
  const declaredHt = detail.montant_ht_total || 0
  const calculatedHt = detail.montant_ht_calcule || 0
  const ecartHt = declaredHt - calculatedHt
  const hasEcart = Math.abs(ecartHt) > 100

  return (
    <div className={`rounded-xl border p-4 ${hasEcart ? 'bg-red-50 border-red-200' : 'bg-white border-slate-200'}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-slate-700">Réconciliation</span>
        {hasEcart && (
          <span className="text-xs font-medium text-red-600 px-2 py-0.5 bg-red-100 rounded">
            Écart détecté
          </span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <span className="text-slate-400 text-xs block">Déclaré HT</span>
          <span className="text-slate-700 font-mono">{formatCents(declaredHt)}</span>
        </div>
        <div>
          <span className="text-slate-400 text-xs block">Calculé HT</span>
          <span className="text-slate-700 font-mono">{formatCents(calculatedHt)}</span>
        </div>
        <div>
          <span className="text-slate-400 text-xs block">Écart</span>
          <span className={`font-mono ${hasEcart ? 'text-red-600 font-medium' : 'text-green-600'}`}>
            {formatCents(ecartHt)}
          </span>
        </div>
      </div>
    </div>
  )
}
