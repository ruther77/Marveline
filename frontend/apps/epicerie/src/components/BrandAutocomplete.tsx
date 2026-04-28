/**
 * Autocomplete marque avec suggestions du BrandDictionary.
 *
 * Input texte libre avec dropdown de suggestions fuzzy.
 * L'opérateur peut taper une marque libre ou choisir dans la liste.
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { suggestBrand } from '@/api/etl_imports'

interface BrandAutocompleteProps {
  value: string | null
  onChange: (brand: string) => void
  onCategoryHint?: (code: string) => void
  alert?: 'error' | 'warning' | null
}

export default function BrandAutocomplete({
  value,
  onChange,
  onCategoryHint,
  alert,
}: BrandAutocompleteProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value || '')
  const [showDropdown, setShowDropdown] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const { data: suggestData } = useQuery({
    queryKey: ['etl-suggest-brand', draft],
    queryFn: () => suggestBrand(draft, 8),
    enabled: editing && draft.length >= 2,
    staleTime: 30_000,
  })
  const suggestions = suggestData?.suggestions ?? []

  const handleFocus = useCallback(() => {
    setDraft(value || '')
    setEditing(true)
    setShowDropdown(true)
  }, [value])

  const handleBlur = useCallback(() => {
    // Commit synchrone — les suggestions utilisent onMouseDown+preventDefault,
    // le focus reste sur l'input donc handleBlur n'est pas déclenché par un clic suggestion.
    // Un setTimeout ici crée une race avec le bouton Valider (PATCH skippé).
    setEditing(false)
    setShowDropdown(false)
    if (draft.trim() && draft.trim() !== (value || '')) {
      onChange(draft.trim())
    }
  }, [draft, value, onChange])

  const handleSelect = useCallback((name: string, categories: string[]) => {
    onChange(name)
    setDraft(name)
    setEditing(false)
    setShowDropdown(false)
    // Si marque mono-catégorie, suggérer la catégorie
    if (categories.length === 1 && onCategoryHint) {
      onCategoryHint(categories[0])
    }
  }, [onChange, onCategoryHint])

  // Close on outside click
  useEffect(() => {
    if (!showDropdown) return
    function handle(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
        setEditing(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [showDropdown])

  const alertCls = alert === 'warning' ? 'bg-amber-50' : ''

  if (editing) {
    return (
      <div ref={containerRef} className="relative">
        <input
          ref={inputRef}
          type="text"
          value={draft}
          onChange={e => { setDraft(e.target.value); setShowDropdown(true) }}
          onBlur={handleBlur}
          onKeyDown={e => {
            if (e.key === 'Enter') inputRef.current?.blur()
            if (e.key === 'Escape') { setEditing(false); setShowDropdown(false) }
          }}
          autoFocus
          placeholder="Marque..."
          className="w-full px-2 py-1 text-[11px] border border-emerald-500 rounded outline-none"
        />
        {showDropdown && suggestions.length > 0 && (
          <div className="absolute z-30 top-full mt-1 left-0 w-48 bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
            {suggestions.map(s => (
              <button
                key={s.name}
                onMouseDown={e => { e.preventDefault(); handleSelect(s.name, s.categories) }}
                className="w-full text-left px-2 py-1 text-[11px] hover:bg-slate-50 flex items-center justify-between"
              >
                <span className="text-slate-700 font-medium truncate">{s.name}</span>
                <span className="text-[9px] text-slate-400 shrink-0 ml-1">×{s.usage_count}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={handleFocus}
      className={`w-full text-left px-2 py-1 text-[11px] rounded cursor-pointer hover:bg-slate-100 transition-colors truncate ${alertCls} ${
        value ? 'text-slate-700' : 'text-slate-400'
      }`}
    >
      {value || '+ Marque'}
    </button>
  )
}
