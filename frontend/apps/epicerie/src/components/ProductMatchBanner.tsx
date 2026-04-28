/**
 * Bannière "Produit similaire trouvé" affichée sous une ligne d'import.
 *
 * Affiche jusqu'à 3 matches similaires depuis le catalogue, chacun cliquable
 * pour appliquer EAN/marque/catégorie/conditionnement/volume/prix/TVA en 1 clic.
 * Les champs déjà remplis ne sont jamais écrasés (LigneRow décide).
 */
import { useState } from 'react'
import { Package, ArrowRight, ChevronDown, ChevronUp } from 'lucide-react'
import type { SimilarProduct } from '@/types/etl_import'

interface ProductMatchBannerProps {
  matches: SimilarProduct[]
  onApply: (match: SimilarProduct) => void
}

function appliableFields(m: SimilarProduct): string[] {
  const a: string[] = []
  if (m.ean) a.push('EAN')
  if (m.categorie_code) a.push('Cat.')
  if (m.marque) a.push('Marque')
  if (m.conditionnement) a.push('Cond.')
  if (m.volume_unitaire_ml) a.push('Vol.')
  if (m.prix_unitaire_cts) a.push('Prix')
  return a
}

function MatchRow({ m, onApply, badgeLabel }: {
  m: SimilarProduct
  onApply: (m: SimilarProduct) => void
  badgeLabel?: string
}) {
  const scorePct = Math.round(m.score * 100)
  const appliable = appliableFields(m)
  return (
    <div className="flex items-center gap-2 text-[10px] py-0.5">
      <Package className="h-3 w-3 text-violet-500 shrink-0" />
      {badgeLabel && (
        <span className="text-[9px] font-bold text-violet-500 uppercase tracking-wider shrink-0">
          {badgeLabel}
        </span>
      )}
      <span className="text-violet-700 truncate flex-1">
        <strong>{m.designation}</strong>
        {m.ean && <span className="text-violet-400 ml-1 font-mono">{m.ean}</span>}
        <span className="text-violet-400 ml-1">({scorePct}%)</span>
      </span>
      {appliable.length > 0 && (
        <span className="text-violet-500/70 text-[9px] shrink-0">
          {appliable.join(', ')}
        </span>
      )}
      <button
        onClick={() => onApply(m)}
        className="flex items-center gap-0.5 text-[10px] font-semibold text-violet-600 hover:text-violet-800 hover:underline shrink-0"
      >
        Appliquer <ArrowRight className="h-2.5 w-2.5" />
      </button>
    </div>
  )
}

export default function ProductMatchBanner({ matches, onApply }: ProductMatchBannerProps) {
  const [expanded, setExpanded] = useState(false)
  if (matches.length === 0) return null

  const visible = expanded ? matches.slice(0, 3) : [matches[0]]

  return (
    <tr>
      <td colSpan={20} className="px-3 py-1.5 bg-violet-50/50">
        <div className="flex flex-col gap-0.5">
          {visible.map((m, i) => (
            <MatchRow
              key={m.candidate_id}
              m={m}
              onApply={onApply}
              badgeLabel={expanded && matches.length > 1 ? `#${i + 1}` : undefined}
            />
          ))}
          {matches.length > 1 && (
            <button
              onClick={() => setExpanded(e => !e)}
              className="flex items-center gap-0.5 text-[9px] text-violet-500/70 hover:text-violet-700 self-start ml-5"
            >
              {expanded ? (
                <>
                  <ChevronUp className="h-2.5 w-2.5" /> Replier
                </>
              ) : (
                <>
                  <ChevronDown className="h-2.5 w-2.5" />
                  {Math.min(matches.length - 1, 2)} autre{matches.length > 2 ? 's match' : ' match'} disponible{matches.length > 2 ? 's' : ''}
                </>
              )}
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}
