// Barre d'actions batch — catégorie, marque, EAN en masse + suppression

import { useEffect, useRef, useState } from 'react'
import type { CategoryGroup } from '@/types/etl_import'

interface BatchActionsBarProps {
  count: number
  groups: CategoryGroup[]
  onBatchCategory: (code: string) => void
  onBatchBrand: (marque: string) => void
  onBatchEan: (ean: string) => void
  onBatchDelete: () => void
}

export default function BatchActionsBar({
  count, groups,
  onBatchCategory, onBatchBrand, onBatchEan, onBatchDelete,
}: BatchActionsBarProps) {
  const [showCatPicker, setShowCatPicker] = useState(false)
  const [showBrandInput, setShowBrandInput] = useState(false)
  const [showEanInput, setShowEanInput] = useState(false)
  const [brandDraft, setBrandDraft] = useState('')
  const [eanDraft, setEanDraft] = useState('')
  const brandRef = useRef<HTMLInputElement | null>(null)
  const eanRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => { if (showBrandInput) brandRef.current?.focus() }, [showBrandInput])
  useEffect(() => { if (showEanInput) eanRef.current?.focus() }, [showEanInput])

  if (count === 0) return null

  const applyBrand = () => {
    const v = brandDraft.trim().toUpperCase()
    if (v) { onBatchBrand(v); setBrandDraft(''); setShowBrandInput(false) }
  }
  const applyEan = () => {
    const v = eanDraft.trim()
    if (v && /^\d{8,14}$/.test(v)) { onBatchEan(v); setEanDraft(''); setShowEanInput(false) }
  }

  return (
    <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-2">
      <span className="text-sm text-emerald-700 font-medium">
        {count} ligne{count > 1 ? 's' : ''} sélectionnée{count > 1 ? 's' : ''}
      </span>
      <div className="flex-1" />

      {/* Catégorie */}
      <div className="relative">
        <button
          onClick={() => { setShowCatPicker(v => !v); setShowBrandInput(false); setShowEanInput(false) }}
          className="px-3 py-1 bg-white border border-emerald-300 text-emerald-700 text-xs rounded-lg hover:bg-emerald-50 transition-colors"
        >
          Catégorie…
        </button>
        {showCatPicker && (
          <div className="absolute z-50 right-0 top-full mt-1 w-56 bg-white rounded-lg border border-slate-200 shadow-lg max-h-64 overflow-y-auto">
            {groups.map(g => (
              <div key={g.group}>
                <div className="px-2 py-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider bg-slate-50">
                  {g.label}
                </div>
                {g.items.map(item => (
                  <button
                    key={item.code}
                    onClick={() => { onBatchCategory(item.code); setShowCatPicker(false) }}
                    className="w-full text-left px-3 py-1.5 text-xs text-slate-600 hover:bg-emerald-50 transition-colors"
                  >
                    <span className="font-mono text-[10px] text-slate-400 mr-1.5">{item.code}</span>
                    {item.label}
                  </button>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Marque */}
      <div className="relative">
        <button
          onClick={() => { setShowBrandInput(v => !v); setShowCatPicker(false); setShowEanInput(false) }}
          className="px-3 py-1 bg-white border border-violet-300 text-violet-700 text-xs rounded-lg hover:bg-violet-50 transition-colors"
        >
          Marque…
        </button>
        {showBrandInput && (
          <div className="absolute z-50 right-0 top-full mt-1 w-64 bg-white rounded-lg border border-slate-200 shadow-lg p-2">
            <input
              ref={brandRef}
              value={brandDraft}
              onChange={e => setBrandDraft(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') applyBrand(); if (e.key === 'Escape') setShowBrandInput(false) }}
              placeholder="ex: MAGGI"
              className="w-full text-xs px-2 py-1 border border-slate-300 rounded"
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={applyBrand}
                className="flex-1 px-2 py-1 bg-violet-600 text-white text-xs rounded hover:bg-violet-700"
              >
                Appliquer à {count} ligne{count > 1 ? 's' : ''}
              </button>
              <button
                onClick={() => { setShowBrandInput(false); setBrandDraft('') }}
                className="px-2 py-1 text-xs text-slate-500 hover:text-slate-700"
              >
                Annuler
              </button>
            </div>
          </div>
        )}
      </div>

      {/* EAN */}
      <div className="relative">
        <button
          onClick={() => { setShowEanInput(v => !v); setShowCatPicker(false); setShowBrandInput(false) }}
          className="px-3 py-1 bg-white border border-blue-300 text-blue-700 text-xs rounded-lg hover:bg-blue-50 transition-colors"
          title="Applique le même EAN aux lignes sélectionnées (déconseillé sauf produits identiques)"
        >
          EAN…
        </button>
        {showEanInput && (
          <div className="absolute z-50 right-0 top-full mt-1 w-64 bg-white rounded-lg border border-slate-200 shadow-lg p-2">
            <input
              ref={eanRef}
              value={eanDraft}
              onChange={e => setEanDraft(e.target.value.replace(/\D/g, ''))}
              onKeyDown={e => { if (e.key === 'Enter') applyEan(); if (e.key === 'Escape') setShowEanInput(false) }}
              placeholder="8 à 14 chiffres"
              className="w-full text-xs px-2 py-1 border border-slate-300 rounded font-mono"
              maxLength={14}
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={applyEan}
                disabled={!/^\d{8,14}$/.test(eanDraft.trim())}
                className="flex-1 px-2 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed"
              >
                Appliquer à {count} ligne{count > 1 ? 's' : ''}
              </button>
              <button
                onClick={() => { setShowEanInput(false); setEanDraft('') }}
                className="px-2 py-1 text-xs text-slate-500 hover:text-slate-700"
              >
                Annuler
              </button>
            </div>
          </div>
        )}
      </div>

      <button
        onClick={onBatchDelete}
        className="px-3 py-1 bg-red-50 border border-red-200 text-red-600 text-xs rounded-lg hover:bg-red-100 transition-colors"
      >
        Supprimer
      </button>
    </div>
  )
}
