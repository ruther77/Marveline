// Ligne table éditable — une ligne de facture avec tous les champs

import EditableCell from './EditableCell'
import EuroInput from '@/components/EuroInput'
import CategorySuggestDropdown from '@/components/CategorySuggestDropdown'
import BrandAutocomplete from '@/components/BrandAutocomplete'
import ProductMatchBanner from '@/components/ProductMatchBanner'
import AutoFillBadge from '@/components/etl/AutoFillBadge'
import { FIELD_ACTION_LABELS } from '@/types/etl_import'
import { formatCents } from '@/utils/etl-helpers'
import type { LigneFactureRead, CategoryGroup, LigneFieldAlerts } from '@/types/etl_import'

export interface TableActions {
  onUpdateLigne: (idx: number, field: string, value: string | number) => void
  onDeleteLigne: (idx: number) => void
  onToggleSelect: (idx: number) => void
  onSelectLine?: (idx: number) => void
  /** Feedback après clic "Appliquer" du ProductMatchBanner. */
  onMatchApplied?: (idx: number, fieldsApplied: string[]) => void
  /** Révoque un auto-fill : vide le champ et retire la méta. */
  onRevokeAutoFill?: (idx: number, field: string) => void
}

export interface KeyboardNav {
  registerCell: (row: number, col: number, el: HTMLElement | null) => void
  handleCellKeyDown: (e: React.KeyboardEvent, row: number, col: number) => void
}

interface LigneRowProps {
  l: LigneFactureRead
  fields: LigneFieldAlerts
  issueCount: number
  confidenceColor: string
  isPreview: boolean
  isPostValidatedEditing?: boolean
  isRecentlyCorrected?: boolean
  isSelected: boolean
  isHighlighted: boolean
  groups: CategoryGroup[]
  actions: TableActions
  keyboard?: KeyboardNav
}

export default function LigneRow({
  l, fields: f, issueCount, confidenceColor,
  isPreview, isPostValidatedEditing = false, isRecentlyCorrected = false,
  isSelected, isHighlighted,
  groups, actions, keyboard,
}: LigneRowProps) {
  const cs = l.confidence_score ?? 0
  const tooltip = `Confiance : ${cs}/100` + (issueCount > 0 ? ` — ${issueCount} champ${issueCount > 1 ? 's' : ''} à corriger` : '')
  const isEditableFinance = isPreview || isPostValidatedEditing

  return (
    <>
      <tr
        onClick={() => actions.onSelectLine?.(l.idx)}
        className={`border-t border-slate-100 transition-all ${
          isRecentlyCorrected
            ? 'bg-emerald-50/60 border-l-[3px] border-l-emerald-500'
            : isHighlighted
              ? 'bg-violet-50 border-l-[3px] border-l-violet-500'
              : isSelected ? 'bg-emerald-50/50' : 'hover:bg-slate-50'
        }`}
      >
        {isPreview && (
          <td className="px-2 py-1.5">
            <input type="checkbox" checked={isSelected} onChange={() => actions.onToggleSelect(l.idx)} className="rounded border-slate-300" />
          </td>
        )}
        <td className="px-1 py-1.5">
          <span className={`w-2.5 h-2.5 rounded-full inline-block ${confidenceColor}`} title={tooltip} />
        </td>
        <td className="px-3 py-1.5 font-medium text-slate-800 max-w-[200px]">
          {isPreview
            ? <EditableCell value={l.designation || l.designation_raw || ''} onChange={val => actions.onUpdateLigne(l.idx, 'designation', val)} placeholder={l.designation_raw ? `OCR: ${l.designation_raw}` : undefined} cellRef={el => keyboard?.registerCell(l.idx, 0, el)} onKeyNav={e => keyboard?.handleCellKeyDown(e, l.idx, 0)} />
            : <span className="truncate block cursor-default" title={isPostValidatedEditing ? 'Non modifiable après validation' : undefined}>{l.designation || l.designation_raw || '—'}</span>
          }
        </td>
        <td className="px-2 py-1.5 font-mono text-[10px]">
          {isPreview
            ? <EditableCell value={l.ean || ''} onChange={val => actions.onUpdateLigne(l.idx, 'ean', val)} alert={f.ean} placeholder={FIELD_ACTION_LABELS.ean} cellRef={el => keyboard?.registerCell(l.idx, 1, el)} onKeyNav={e => keyboard?.handleCellKeyDown(e, l.idx, 1)} />
            : <span className="cursor-default" title={isPostValidatedEditing ? 'Non modifiable après validation' : undefined}>{l.ean || '—'}</span>
          }
          {l.auto_applied_fields?.ean && (
            <div className="mt-0.5">
              <AutoFillBadge meta={l.auto_applied_fields.ean} onRevoke={() => actions.onRevokeAutoFill?.(l.idx, 'ean')} compact />
            </div>
          )}
        </td>
        <td className="px-2 py-1.5 text-slate-500">
          {isEditableFinance ? (
            <BrandAutocomplete value={l.marque ?? null} onChange={val => actions.onUpdateLigne(l.idx, 'marque', val)}
              onCategoryHint={code => { if (!l.categorie_code || l.categorie_code === 'AUTRE') actions.onUpdateLigne(l.idx, 'categorie_code', code) }}
              alert={f.marque} />
          ) : (l.marque || '—')}
          {l.auto_applied_fields?.marque && (
            <div className="mt-0.5">
              <AutoFillBadge meta={l.auto_applied_fields.marque} onRevoke={() => actions.onRevokeAutoFill?.(l.idx, 'marque')} compact />
            </div>
          )}
        </td>
        <td className="px-2 py-1.5">
          {isEditableFinance ? (
            <CategorySuggestDropdown value={l.categorie_code ?? null} designation={l.designation} onChange={val => actions.onUpdateLigne(l.idx, 'categorie_code', val)} groups={groups} alert={f.categorie_code} />
          ) : (
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${l.categorie_code && l.categorie_code !== 'AUTRE' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-400'}`}>{l.categorie_code || 'AUTRE'}</span>
          )}
          {l.auto_applied_fields?.categorie_code && (
            <div className="mt-0.5">
              <AutoFillBadge meta={l.auto_applied_fields.categorie_code} onRevoke={() => actions.onRevokeAutoFill?.(l.idx, 'categorie_code')} compact />
            </div>
          )}
        </td>
        <td className="px-2 py-1.5 text-right font-mono text-slate-700">
          {isEditableFinance ? <EditableCell value={l.quantite ?? ''} type="number" onChange={val => actions.onUpdateLigne(l.idx, 'quantite', Number(val))} className="text-right" alert={f.quantite} placeholder={FIELD_ACTION_LABELS.quantite} cellRef={el => keyboard?.registerCell(l.idx, 2, el)} onKeyNav={e => keyboard?.handleCellKeyDown(e, l.idx, 2)} /> : (l.quantite ?? '—')}
        </td>
        <td className="px-2 py-1.5 text-slate-500">
          {isPreview
            ? <EditableCell value={l.conditionnement || ''} onChange={val => actions.onUpdateLigne(l.idx, 'conditionnement', val)} cellRef={el => keyboard?.registerCell(l.idx, 3, el)} onKeyNav={e => keyboard?.handleCellKeyDown(e, l.idx, 3)} />
            : <span className="cursor-default" title={isPostValidatedEditing ? 'Non modifiable après validation' : undefined}>{l.conditionnement || '—'}</span>
          }
          {l.auto_applied_fields?.conditionnement && (
            <div className="mt-0.5">
              <AutoFillBadge meta={l.auto_applied_fields.conditionnement} onRevoke={() => actions.onRevokeAutoFill?.(l.idx, 'conditionnement')} compact />
            </div>
          )}
        </td>
        <td className="px-2 py-1.5 text-right font-mono text-slate-700">
          {isEditableFinance ? <EuroInput value={l.prix_unitaire_cts ?? null} onChange={val => actions.onUpdateLigne(l.idx, 'prix_unitaire_cts', val)} alert={f.prix_unitaire_cts} placeholder="0.00" /> : formatCents(l.prix_unitaire_cts)}
          {l.prix_catalogue_actuel_cts != null && l.prix_unitaire_cts != null && l.prix_catalogue_actuel_cts !== l.prix_unitaire_cts && (() => {
            const diff = l.prix_unitaire_cts - l.prix_catalogue_actuel_cts
            const pct = l.prix_catalogue_actuel_cts > 0 ? Math.round((diff / l.prix_catalogue_actuel_cts) * 100) : 0
            return (
              <div className={`text-[9px] mt-0.5 ${diff > 0 ? 'text-red-500' : 'text-emerald-600'}`}>
                {formatCents(l.prix_catalogue_actuel_cts)} → {diff > 0 ? '+' : ''}{pct}%
              </div>
            )
          })()}
          {l.prix_catalogue_actuel_cts == null && l.prix_unitaire_cts != null && l.ean && (
            <div className="text-[9px] mt-0.5 text-violet-500">Nouveau</div>
          )}
        </td>
        <td className="px-2 py-1.5 text-right font-mono text-slate-700">{formatCents(l.montant_ht_cts)}</td>
        <td className="px-2 py-1.5 text-right font-mono text-slate-400 text-[10px]">{l.taux_tva_centieme ? `${(l.taux_tva_centieme / 100).toFixed(1)}%` : '—'}</td>
        {isPreview && (
          <td className="px-2 py-1.5">
            <button onClick={() => actions.onDeleteLigne(l.idx)} className="text-red-400 hover:text-red-600 transition-colors text-sm" title="Supprimer">×</button>
          </td>
        )}
      </tr>
      {isPreview && l.similar_products && l.similar_products.length > 0 && (
        <ProductMatchBanner
          matches={l.similar_products}
          onApply={match => {
            // N'écrase pas les valeurs déjà saisies par l'opérateur.
            const applied: string[] = []
            if (match.ean && !l.ean) { actions.onUpdateLigne(l.idx, 'ean', match.ean); applied.push('EAN') }
            if (match.categorie_code && (!l.categorie_code || l.categorie_code === 'AUTRE')) {
              actions.onUpdateLigne(l.idx, 'categorie_code', match.categorie_code); applied.push('catégorie')
            }
            if (match.marque && !l.marque) { actions.onUpdateLigne(l.idx, 'marque', match.marque); applied.push('marque') }
            if (match.conditionnement && !l.conditionnement) {
              actions.onUpdateLigne(l.idx, 'conditionnement', match.conditionnement); applied.push('conditionnement')
            }
            if (match.prix_unitaire_cts && !l.prix_unitaire_cts) {
              actions.onUpdateLigne(l.idx, 'prix_unitaire_cts', match.prix_unitaire_cts); applied.push('prix')
            }
            if (match.taux_tva_centieme && !l.taux_tva_centieme) {
              actions.onUpdateLigne(l.idx, 'taux_tva_centieme', match.taux_tva_centieme); applied.push('TVA')
            }
            actions.onMatchApplied?.(l.idx, applied)
          }}
        />
      )}
    </>
  )
}
