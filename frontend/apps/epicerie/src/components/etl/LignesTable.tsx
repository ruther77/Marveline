// Table éditable des lignes — groupées par statut (erreurs > warnings > valides)

import { useState, useMemo } from 'react'
import LigneRow from './LigneRow'
import type { TableActions, KeyboardNav } from './LigneRow'
import { useTableKeyboardNav } from '@/hooks/useTableKeyboardNav'
import { validateLigne } from '@/types/etl_import'
import type { LigneFactureRead, LigneValidationStatus, CategoryGroup } from '@/types/etl_import'

interface LignesTableProps {
  lignes: LigneFactureRead[]
  groups: CategoryGroup[]
  isPreview: boolean
  isPostValidatedEditing?: boolean
  recentlyCorrectedIdxs?: Set<number>
  selectedIdxs: Set<number>
  selectedLineIdx?: number | null
  actions: TableActions
  onToggleAll: () => void
  filter: LigneValidationStatus | 'all'
}

export default function LignesTable({
  lignes, groups, isPreview, isPostValidatedEditing = false,
  recentlyCorrectedIdxs, selectedIdxs,
  selectedLineIdx, actions, onToggleAll, filter,
}: LignesTableProps) {
  const filtered = useMemo(() => {
    if (filter === 'all') return lignes
    return lignes.filter(l => validateLigne(l).status === filter)
  }, [lignes, filter])

  const grouped = useMemo(() => {
    const errors: LigneFactureRead[] = []
    const warnings: LigneFactureRead[] = []
    const valids: LigneFactureRead[] = []
    for (const l of filtered) {
      const s = validateLigne(l).status
      if (s === 'error') errors.push(l)
      else if (s === 'warning') warnings.push(l)
      else valids.push(l)
    }
    const byConf = (a: LigneFactureRead, b: LigneFactureRead) => (a.confidence_score ?? 0) - (b.confidence_score ?? 0)
    errors.sort(byConf)
    warnings.sort(byConf)
    return { errors, warnings, valids }
  }, [filtered])

  const [collapsedValid, setCollapsedValid] = useState(true)
  const { registerCell, handleCellKeyDown } = useTableKeyboardNav()
  const keyboard: KeyboardNav = { registerCell, handleCellKeyDown }

  const allSelected = filtered.length > 0 && filtered.every(l => selectedIdxs.has(l.idx))
  const colCount = isPreview ? 12 : 10

  const renderRow = (l: LigneFactureRead) => {
    const v = validateLigne(l)
    const dotColor = v.status === 'valid' ? 'bg-green-500' : v.status === 'warning' ? 'bg-amber-500' : 'bg-red-500'
    return (
      <LigneRow key={l.idx} l={l} fields={v.fields} issueCount={v.issueCount}
        confidenceColor={dotColor} isPreview={isPreview}
        isPostValidatedEditing={isPostValidatedEditing}
        isRecentlyCorrected={recentlyCorrectedIdxs?.has(l.idx) ?? false}
        isSelected={selectedIdxs.has(l.idx)} isHighlighted={selectedLineIdx === l.idx}
        groups={groups} actions={actions} keyboard={keyboard} />
    )
  }

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-slate-50">
            <tr>
              {isPreview && (
                <th className="w-8 px-2 py-2">
                  <input type="checkbox" checked={allSelected} onChange={onToggleAll} className="rounded border-slate-300" />
                </th>
              )}
              <th className="w-6 px-1 py-2" />
              <th className="text-left px-3 py-2 font-medium text-slate-500">Produit</th>
              <th className="text-left px-2 py-2 font-medium text-slate-500">EAN</th>
              <th className="text-left px-2 py-2 font-medium text-slate-500">Marque</th>
              <th className="text-left px-2 py-2 font-medium text-slate-500">Cat.</th>
              <th className="text-right px-2 py-2 font-medium text-slate-500">Qte</th>
              <th className="text-left px-2 py-2 font-medium text-slate-500">Cond.</th>
              <th className="text-right px-2 py-2 font-medium text-slate-500">PU HT</th>
              <th className="text-right px-2 py-2 font-medium text-slate-500">Total HT</th>
              <th className="text-right px-2 py-2 font-medium text-slate-500">TVA</th>
              {isPreview && <th className="w-8 px-2 py-2" />}
            </tr>
          </thead>
          <tbody>
            {grouped.errors.length > 0 && (
              <tr><td colSpan={colCount} className="px-3 py-1.5 bg-red-50 border-y border-red-200 text-[10px] font-semibold text-red-700 uppercase tracking-wider">
                À corriger — {grouped.errors.length} ligne{grouped.errors.length > 1 ? 's' : ''}
              </td></tr>
            )}
            {grouped.errors.map(renderRow)}

            {grouped.warnings.length > 0 && (
              <tr><td colSpan={colCount} className="px-3 py-1.5 bg-amber-50 border-y border-amber-200 text-[10px] font-semibold text-amber-700 uppercase tracking-wider">
                À vérifier — {grouped.warnings.length} ligne{grouped.warnings.length > 1 ? 's' : ''}
              </td></tr>
            )}
            {grouped.warnings.map(renderRow)}

            {grouped.valids.length > 0 && (
              <tr>
                <td colSpan={colCount} className="px-3 py-1.5 bg-emerald-50 border-y border-emerald-200">
                  <button onClick={() => setCollapsedValid(v => !v)} className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wider hover:underline">
                    {collapsedValid ? '▸' : '▾'} Validées — {grouped.valids.length} ligne{grouped.valids.length > 1 ? 's' : ''} {collapsedValid ? '(cliquer pour détailler)' : ''}
                  </button>
                </td>
              </tr>
            )}
            {!collapsedValid && grouped.valids.map(renderRow)}

            {filtered.length === 0 && (
              <tr>
                <td colSpan={colCount} className="px-4 py-6 text-center text-slate-400 text-sm">
                  Aucune ligne {filter !== 'all' ? `avec statut "${filter}"` : ''}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
