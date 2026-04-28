/**
 * Dropdown catégorie avec suggestions KNN.
 *
 * Mode hybride :
 *   - Suggestions IA en tête (top-3 KNN basées sur la désignation)
 *   - Recherche manuelle parmi les 91 catégories
 */
import { useState, useMemo, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Sparkles } from 'lucide-react'
import { suggestCategory } from '@/api/etl_imports'
import type { CategorySuggestion } from '@/api/etl_imports'
import type { CategoryGroup } from '@/types/etl_import'

interface CategorySuggestDropdownProps {
  value: string | null
  designation: string
  groups: CategoryGroup[]
  onChange: (code: string) => void
  alert?: 'error' | 'warning' | null
}

export default function CategorySuggestDropdown({
  value,
  designation,
  groups,
  onChange,
  alert,
}: CategorySuggestDropdownProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)

  // Suggestions KNN (lazy-loaded au premier open)
  const { data: suggestData } = useQuery({
    queryKey: ['etl-suggest-category', designation],
    queryFn: () => suggestCategory(designation, 3),
    enabled: open && designation.length >= 3,
    staleTime: 60_000,
  })
  const suggestions: CategorySuggestion[] = suggestData?.suggestions ?? []

  // Filtre local
  const filtered = useMemo(() => {
    if (!search) return groups
    const q = search.toLowerCase()
    return groups
      .map(g => ({
        ...g,
        items: g.items.filter(i =>
          i.code.toLowerCase().includes(q) || i.label.toLowerCase().includes(q),
        ),
      }))
      .filter(g => g.items.length > 0)
  }, [groups, search])

  // Close on click outside
  useEffect(() => {
    if (!open) return
    function handle(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  // Label du code sélectionné
  const selectedLabel = useMemo(() => {
    if (!value) return null
    for (const g of groups) {
      for (const i of g.items) {
        if (i.code === value) return i.label
      }
    }
    return value
  }, [value, groups])

  const alertCls = alert === 'error'
    ? 'bg-red-600/[.08] border-red-300'
    : alert === 'warning'
      ? 'bg-amber-50 border-amber-300'
      : 'border-slate-200'

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className={`w-full flex items-center justify-between gap-1 px-2 py-1 text-[11px] border rounded cursor-pointer transition-colors ${alertCls} ${
          value ? 'text-slate-700' : 'text-slate-400'
        }`}
      >
        <span className="truncate">{selectedLabel || value || '+ Cat.'}</span>
        <ChevronDown className="h-3 w-3 shrink-0 text-slate-400" />
      </button>

      {open && (
        <div className="absolute z-30 top-full mt-1 left-0 w-64 bg-white border border-slate-200 rounded-xl shadow-lg max-h-72 flex flex-col overflow-hidden">
          {/* Search */}
          <div className="p-2 border-b border-slate-100">
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Rechercher..."
              autoFocus
              className="w-full px-2 py-1 text-[11px] border border-slate-200 rounded focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div className="overflow-y-auto flex-1">
            {/* Suggestions KNN */}
            {suggestions.length > 0 && !search && (
              <div className="px-2 py-1.5 border-b border-slate-100">
                <div className="flex items-center gap-1 text-[9px] text-violet-600 font-semibold uppercase tracking-wider mb-1">
                  <Sparkles className="h-3 w-3" /> Suggestions
                </div>
                {suggestions.map(s => (
                  <button
                    key={s.code}
                    onClick={() => { onChange(s.code); setOpen(false); setSearch('') }}
                    className={`w-full flex items-center justify-between px-2 py-1 text-[11px] rounded hover:bg-violet-50 transition-colors ${
                      value === s.code ? 'bg-violet-50 font-semibold text-violet-700' : 'text-slate-700'
                    }`}
                  >
                    <span className="truncate">{s.label}</span>
                    <span className="text-[9px] text-slate-400 font-mono shrink-0 ml-1">{Math.round(s.score * 100)}%</span>
                  </button>
                ))}
              </div>
            )}

            {/* All categories grouped */}
            {filtered.map(g => (
              <div key={g.group} className="px-2 py-1">
                <div className="text-[9px] text-slate-400 font-semibold uppercase tracking-wider mb-0.5">{g.label}</div>
                {g.items.map(i => (
                  <button
                    key={i.code}
                    onClick={() => { onChange(i.code); setOpen(false); setSearch('') }}
                    className={`w-full text-left px-2 py-0.5 text-[11px] rounded hover:bg-slate-50 ${
                      value === i.code ? 'bg-emerald-50 font-semibold text-emerald-700' : 'text-slate-600'
                    }`}
                  >
                    {i.label} <span className="text-slate-400 text-[9px]">{i.code}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
