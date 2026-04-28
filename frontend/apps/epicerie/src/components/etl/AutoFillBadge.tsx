/**
 * Badge discret sous/à côté d'un champ auto-rempli par le pipeline ETL.
 *
 * Affiche la source (match par norme, code article, historique, TF-IDF) et le
 * score de confiance. Clic sur la croix = demande de révocation (le parent
 * vide le champ pour laisser l'opérateur saisir ou ré-ouvre la suggestion).
 */
import { X } from 'lucide-react'
import type { AutoAppliedFieldMeta, AutoFillSource } from '@/types/etl_import'

const SOURCE_LABEL: Record<AutoFillSource, string> = {
  norm_exact: 'Nom identique',
  article_four: 'Code fournisseur',
  correction_history: 'Correction passée',
  tfidf_auto: 'Similarité élevée',
  tfidf_auto_soft: 'Similarité',
  off_import: 'OpenFoodFacts',
}

const SOURCE_COLOR: Record<AutoFillSource, string> = {
  norm_exact: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  article_four: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  correction_history: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  tfidf_auto: 'bg-sky-100 text-sky-700 border-sky-200',
  tfidf_auto_soft: 'bg-amber-100 text-amber-700 border-amber-200',
  off_import: 'bg-teal-100 text-teal-700 border-teal-200',
}

interface AutoFillBadgeProps {
  meta: AutoAppliedFieldMeta
  onRevoke?: () => void
  compact?: boolean
}

export default function AutoFillBadge({ meta, onRevoke, compact = false }: AutoFillBadgeProps) {
  const pct = Math.round((meta.score ?? 0) * 100)
  const label = SOURCE_LABEL[meta.source] ?? meta.source
  const color = SOURCE_COLOR[meta.source] ?? 'bg-slate-100 text-slate-600 border-slate-200'
  const tooltip = `Auto-rempli (${label}) — ${pct}%${
    meta.candidate_designation ? `\nDepuis : ${meta.candidate_designation}` : ''
  }`
  return (
    <span
      title={tooltip}
      className={`inline-flex items-center gap-1 rounded border ${compact ? 'px-1 py-0' : 'px-1.5 py-0.5'} ${color} text-[9px] font-medium leading-none`}
    >
      <span>auto {pct}%</span>
      {onRevoke && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRevoke() }}
          className="opacity-60 hover:opacity-100 transition-opacity"
          title="Annuler l'auto-remplissage"
          aria-label="Annuler l'auto-remplissage"
        >
          <X className="h-2 w-2" />
        </button>
      )}
    </span>
  )
}
