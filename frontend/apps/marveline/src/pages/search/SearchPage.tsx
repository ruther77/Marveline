import { PageHeader } from '@/components/PageHeader'
import { useCallback, useMemo, useRef } from 'react'
import { useNavigate, useSearch as useRouterSearch } from '@tanstack/react-router'
import { Search, X } from 'lucide-react'
import { useSearch } from '@/api/queries/useSearch'
import { useDebounce } from '@/hooks/useDebounce'
import type { SearchResult, SearchResultType } from '@/types/search'
import type { SearchPageSearch } from '@/routes/_app/search'

// ── Config ────────────────────────────────────────────────────────────────────

const ALL_TYPES: { value: SearchResultType; label: string; activeClass: string }[] = [
  { value: 'customer',    label: 'Clients',      activeClass: 'bg-blue-900/40 text-blue-400 border-blue-700/50' },
  { value: 'product',     label: 'Produits',     activeClass: 'bg-green-900/40 text-green-400 border-green-700/50' },
  { value: 'reservation', label: 'Réservations', activeClass: 'bg-purple-900/40 text-purple-400 border-purple-700/50' },
  { value: 'invoice',     label: 'Factures',     activeClass: 'bg-orange-900/40 text-orange-400 border-orange-700/50' },
  { value: 'devis',       label: 'Devis',        activeClass: 'bg-dark-600/80 text-dark-300 border-dark-500' },
]

const TYPE_BADGE: Record<SearchResultType, string> = {
  customer:    'bg-blue-900/30 text-blue-400',
  product:     'bg-green-900/30 text-green-400',
  reservation: 'bg-purple-900/30 text-purple-400',
  invoice:     'bg-orange-900/30 text-orange-400',
  devis:       'bg-dark-900 text-dark-300',
}

const TYPE_LABEL: Record<SearchResultType, string> = {
  customer: 'Client', product: 'Produit', reservation: 'Réservation',
  invoice: 'Facture', devis: 'Devis',
}

function groupByType(results: SearchResult[]): Map<SearchResultType, SearchResult[]> {
  const map = new Map<SearchResultType, SearchResult[]>()
  for (const r of results) {
    const list = map.get(r.type) ?? []
    list.push(r)
    map.set(r.type, list)
  }
  return map
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SearchPage() {
  const navigate = useNavigate({ from: '/search' })
  const { q = '', types: rawTypes } = useRouterSearch({ strict: false }) as {
    q?: string
    types?: SearchResultType | SearchResultType[]
  }

  // Normalisation : string | string[] | undefined → SearchResultType[]
  const activeTypes: SearchResultType[] = useMemo(
    () =>
      Array.isArray(rawTypes)
        ? rawTypes
        : rawTypes
          ? [rawTypes]
          : [],
    [rawTypes]
  )

  const setQ = useCallback(
    (val: string) =>
      navigate({ search: (prev: SearchPageSearch): SearchPageSearch => ({ ...prev, q: val }) }),
    [navigate]
  )

  const toggleType = useCallback(
    (type: SearchResultType) => {
      const next = activeTypes.includes(type)
        ? activeTypes.filter((t) => t !== type)
        : [...activeTypes, type]
      navigate({ search: (prev: SearchPageSearch): SearchPageSearch => ({ ...prev, types: next }) })
    },
    [navigate, activeTypes]
  )

  const clearAll = useCallback(
    () => navigate({ search: { q: '', types: [] } as SearchPageSearch }),
    [navigate]
  )

  const debouncedQ = useDebounce(q, 300)
  const typesFilter = activeTypes.length > 0 ? activeTypes : undefined
  const { data, isLoading } = useSearch(debouncedQ, typesFilter)

  const inputRef = useRef<HTMLInputElement>(null)

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Escape') { setQ(''); inputRef.current?.blur() }
    },
    [setQ]
  )

  const grouped = data ? groupByType(data.results) : new Map<SearchResultType, SearchResult[]>()
  const hasInput = q.trim().length >= 1
  const hasClear = q.length > 0 || activeTypes.length > 0

  return (
    <div className="p-4 md:p-6 max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      <PageHeader title="Recherche" />
      {/* Champ de recherche */}
      <div className="flex items-center gap-4 card px-4 py-4">
        <Search className="w-5 h-5 text-dark-500 shrink-0" />
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Rechercher…"
          className="flex-1 text-sm outline-none bg-transparent placeholder-dark-400"
          autoFocus
        />
        {hasClear && (
          <button onClick={clearAll} className="text-dark-500 hover:text-dark-50 p-1 rounded" aria-label="Tout effacer">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Filtres par type */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-dark-500 mr-1">Filtrer :</span>
        {ALL_TYPES.map(({ value, label, activeClass }) => (
          <button
            key={value}
            onClick={() => toggleType(value)}
            className={`text-xs px-4 py-1.5 rounded-full border transition-colors ${
              activeTypes.includes(value)
                ? activeClass
                : 'bg-dark-900 text-dark-400 border-dark-600 hover:border-dark-500'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Skeleton */}
      {isLoading && (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card px-4 py-4 flex items-center gap-4">
              <div className="h-5 skel rounded w-16 shrink-0" />
              <div className="flex-1 space-y-1.5">
                <div className="h-3 skel rounded w-40" />
                <div className="h-2 skel rounded w-56" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Résultats groupés */}
      {!isLoading && data && data.results.length > 0 && (
        <div className="space-y-6">
          <p className="text-xs text-dark-400">
            {data.total} résultat{data.total !== 1 ? 's' : ''}
            {activeTypes.length > 0 && ` · ${activeTypes.map((t) => TYPE_LABEL[t]).join(', ')}`}
          </p>

          {ALL_TYPES.filter(({ value }) => grouped.has(value)).map(({ value, label, activeClass }) => {
            const items = grouped.get(value) ?? []
            return (
              <section key={value} aria-label={label}>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${activeClass}`}>
                    {label}
                  </span>
                  <span className="text-xs text-dark-500">{items.length}</span>
                </div>
                <div className="space-y-1">
                  {items.map((result) => (
                    <button
                      key={`${result.type}-${result.id}`}
                      onClick={() => navigate({ to: result.url as never })}
                      className="w-full text-left card px-4 py-4 hover:bg-dark-600/60 flex items-start gap-4 transition-colors"
                    >
                      <span className={`text-xs font-medium px-2 py-0.5 rounded mt-0.5 shrink-0 ${TYPE_BADGE[result.type]}`}>
                        {TYPE_LABEL[result.type]}
                      </span>
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{result.title}</div>
                        {result.subtitle && (
                          <div className="text-xs text-dark-400 mt-0.5 truncate">{result.subtitle}</div>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              </section>
            )
          })}
        </div>
      )}

      {/* Aucun résultat */}
      {!isLoading && data && hasInput && data.results.length === 0 && (
        <div className="text-center py-12">
          <Search className="w-10 h-10 mx-auto mb-4 text-dark-600" />
          <p className="text-sm text-dark-400">Aucun résultat pour « {q} »</p>
          {activeTypes.length > 0 && (
            <button
              onClick={() => navigate({ search: (prev: SearchPageSearch): SearchPageSearch => ({ ...prev, types: [] }) })}
              className="text-xs text-primary-400 hover:underline mt-2 block mx-auto"
            >
              Chercher dans tous les types
            </button>
          )}
        </div>
      )}

      {/* État initial */}
      {!hasInput && (
        <div className="text-center py-12">
          <Search className="w-10 h-10 mx-auto mb-4 text-dark-600" />
          <p className="text-sm text-dark-500">Saisissez au moins un caractère pour rechercher</p>
          <p className="text-xs text-dark-600 mt-1">Esc pour vider · Cliquez sur un type pour filtrer</p>
        </div>
      )}
    </div>
  )
}
