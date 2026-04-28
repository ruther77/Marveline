// StockPage — Gestion opérationnelle du stock ingrédients
// ADR-14 : stock_actuel lu directement depuis la DB (¬ Redis)
import { useState, useDeferredValue } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ChevronRight, RefreshCw, Settings, ArrowRightLeft } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { StockSideSheet } from '@/components/StockSideSheet'
import DemanderTransfertModal from '@/components/DemanderTransfertModal'
import type { IngredientRead } from '@/types/restaurant-v2'

const _EPICERIE_TENANT_ID_RAW = import.meta.env.VITE_MASSACORP_EPICERIE_TENANT_ID
const EPICERIE_TENANT_ID = Number(_EPICERIE_TENANT_ID_RAW) || 0

// ── Helpers ───────────────────────────────────────────────────────────────────

type FiltreStatut = 'all' | 'rupture' | 'bas' | 'ok'

const CRITICALITY_ORDER: Record<string, number> = { rupture: 0, bas: 1, ok: 2 }

// ── IngRow ────────────────────────────────────────────────────────────────────

function IngRow({
  ing,
  selected,
  onSelect,
}: {
  ing: IngredientRead
  selected: boolean
  onSelect: () => void
}) {
  const statusDot =
    ing.statut === 'rupture'
      ? 'bg-red-500'
      : ing.statut === 'bas'
        ? 'bg-amber-400'
        : 'bg-emerald-400'

  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        'w-full flex items-center gap-3 px-4 py-3.5 text-left transition-colors',
        'border-b border-stone-100 last:border-0',
        selected
          ? 'bg-amber-50 border-l-[3px] border-l-amber-500 pl-[13px]'
          : 'hover:bg-stone-50 border-l-[3px] border-l-transparent',
      ].join(' ')}
    >
      {/* Dot de criticité */}
      <span className={`w-2 h-2 rounded-full shrink-0 ${statusDot}`} />

      {/* Nom + catégorie */}
      <span className="flex-1 min-w-0">
        <span className="text-[13.5px] font-medium text-stone-900 block truncate">{ing.nom}</span>
        {ing.categorie && (
          <span className="text-[11px] text-stone-400">{ing.categorie}</span>
        )}
      </span>

      {/* Stock / seuil */}
      <span className="text-right shrink-0">
        <span
          className={[
            'text-[13px] font-mono font-semibold',
            ing.statut === 'rupture' ? 'text-red-600' : ing.statut === 'bas' ? 'text-amber-600' : 'text-stone-700',
          ].join(' ')}
        >
          {ing.stock_actuel}
        </span>
        <span className="text-[11px] text-stone-400 ml-0.5">
          /{ing.stock_alerte} {ing.unite_stock}
        </span>
      </span>

      <ChevronRight
        className={`h-4 w-4 shrink-0 transition-colors ${selected ? 'text-amber-500' : 'text-stone-300'}`}
      />
    </button>
  )
}

// ── SummaryChip ───────────────────────────────────────────────────────────────

function SummaryChip({
  label,
  count,
  active,
  idle,
  isActive,
  onClick,
}: {
  label: string
  count: number
  active: string
  idle: string
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={[
        'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] font-semibold transition-all',
        isActive ? active : idle,
      ].join(' ')}
    >
      <span className="tabular-nums">{count}</span>
      <span>{label}</span>
    </button>
  )
}

// ── StockPage ─────────────────────────────────────────────────────────────────

export default function StockPage() {
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [filtreCategorie, setFiltreCategorie] = useState<number | undefined>()
  const [filtreStatut, setFiltreStatut] = useState<FiltreStatut>('all')
  const [selectedIngId, setSelectedIngId] = useState<number | null>(null)
  const [showDemanderModal, setShowDemanderModal] = useState(false)

  const { data: ingData, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['restaurant-ingredients', deferredSearch, filtreCategorie],
    queryFn: () =>
      restaurantApi.listIngredients({
        search: deferredSearch || undefined,
        categorie_id: filtreCategorie,
        per_page: 100,
      }),
    staleTime: 30_000,
  })

  const { data: categories } = useQuery({
    queryKey: ['restaurant-categories-ingredient'],
    queryFn: () => restaurantApi.listCategoriesIngredient(),
    staleTime: 60_000,
  })

  const allItems = ingData?.items ?? []
  const rupturesCount = allItems.filter(i => i.statut === 'rupture').length
  const basCount      = allItems.filter(i => i.statut === 'bas').length
  const okCount       = allItems.filter(i => i.statut === 'ok').length

  const filtered = filtreStatut === 'all' ? allItems : allItems.filter(i => i.statut === filtreStatut)
  const sorted = [...filtered].sort((a, b) => {
    const d = CRITICALITY_ORDER[a.statut] - CRITICALITY_ORDER[b.statut]
    return d !== 0 ? d : a.nom.localeCompare(b.nom, 'fr')
  })

  const selectedIng: IngredientRead | null =
    sorted.find(i => i.id === selectedIngId) ??
    allItems.find(i => i.id === selectedIngId) ??
    null

  const toggleStatut = (s: FiltreStatut) =>
    setFiltreStatut(prev => (prev === s ? 'all' : s))

  const hasFilter = !!deferredSearch || !!filtreCategorie || filtreStatut !== 'all'

  return (
    <div className="flex h-screen overflow-hidden bg-stone-50">

      {/* ── Panneau liste ──────────────────────────────────────────────── */}
      <div className={`flex flex-col min-w-0 overflow-hidden ${selectedIng ? 'hidden md:flex md:flex-1' : 'flex-1'}`}>

        {/* Header */}
        <div className="bg-white border-b border-stone-200 px-5 pt-5 pb-4 space-y-4 shrink-0">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h1 className="text-[17px] font-bold text-stone-900 tracking-tight">Stock</h1>
            <div className="flex items-center gap-3">
              {/* BACK-TRANSFER-RESTO-01 — bouton Demander à l'épicerie (backend MVP en place) */}
              <button
                onClick={() => setShowDemanderModal(true)}
                disabled={EPICERIE_TENANT_ID === 0}
                title={EPICERIE_TENANT_ID === 0 ? 'VITE_MASSACORP_EPICERIE_TENANT_ID non configuré' : ''}
                className="flex items-center gap-1.5 h-11 px-4 text-[13px] font-semibold text-white bg-amber-600 rounded-lg hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <ArrowRightLeft className="h-4 w-4" />
                Demander à l'épicerie
              </button>
              <Link
                to="/catalogue"
                className="flex items-center gap-1.5 text-[13px] text-stone-600 hover:text-amber-600 transition-colors min-h-[44px] px-2"
              >
                <Settings className="h-3.5 w-3.5" />
                Catalogue
              </Link>
            </div>
          </div>

          {/* Résumé criticité */}
          <div className="flex items-center gap-2 flex-wrap">
            <SummaryChip
              count={rupturesCount}
              label="rupture"
              isActive={filtreStatut === 'rupture'}
              onClick={() => toggleStatut('rupture')}
              active="bg-red-600 text-white shadow-sm"
              idle="bg-red-50 text-red-600 hover:bg-red-100"
            />
            <SummaryChip
              count={basCount}
              label="bas"
              isActive={filtreStatut === 'bas'}
              onClick={() => toggleStatut('bas')}
              active="bg-amber-500 text-white shadow-sm"
              idle="bg-amber-50 text-amber-600 hover:bg-amber-100"
            />
            <SummaryChip
              count={okCount}
              label="OK"
              isActive={filtreStatut === 'ok'}
              onClick={() => toggleStatut('ok')}
              active="bg-emerald-600 text-white shadow-sm"
              idle="bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
            />

            <button
              onClick={() => refetch()}
              disabled={isFetching}
              aria-label="Actualiser"
              className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] font-medium text-stone-500 hover:text-stone-900 hover:bg-stone-100 transition-colors disabled:opacity-40"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Actualiser</span>
            </button>
          </div>

          {/* Filtres */}
          <div className="flex gap-2">
            <input
              type="search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Rechercher…"
              className="flex-1 min-w-0 bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 placeholder:text-stone-400 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
            />
            <select
              value={filtreCategorie ?? ''}
              onChange={e => setFiltreCategorie(e.target.value ? Number(e.target.value) : undefined)}
              className="bg-stone-50 border border-stone-200 rounded-lg px-2 py-2 text-[13px] text-stone-700 focus:outline-none focus:border-amber-400 transition-colors"
            >
              <option value="">Catégorie</option>
              {categories?.map(c => (
                <option key={c.id} value={c.id}>{c.nom}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Liste */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="h-14 bg-stone-200 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : sorted.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-2">
              <span className="text-2xl">📦</span>
              <p className="text-[13px] text-stone-500">
                {hasFilter ? 'Aucun résultat pour ces filtres.' : 'Aucun ingrédient dans le catalogue.'}
              </p>
              {!hasFilter && (
                <Link to="/catalogue" className="text-[13px] text-amber-600 hover:underline mt-1">
                  Ajouter des ingrédients →
                </Link>
              )}
            </div>
          ) : (
            <div className="bg-white mx-3 my-3 rounded-xl border border-stone-200 overflow-hidden shadow-sm">
              {sorted.map(ing => (
                <IngRow
                  key={ing.id}
                  ing={ing}
                  selected={ing.id === selectedIngId}
                  onSelect={() => setSelectedIngId(ing.id === selectedIngId ? null : ing.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Panneau détail ─────────────────────────────────────────────── */}
      {selectedIng && (
        <StockSideSheet
          key={selectedIng.id}
          ing={selectedIng}
          onClose={() => setSelectedIngId(null)}
        />
      )}

      {/* Modal Demander à l'épicerie */}
      {showDemanderModal && EPICERIE_TENANT_ID > 0 && (
        <DemanderTransfertModal
          epicerieTenantId={EPICERIE_TENANT_ID}
          onClose={() => setShowDemanderModal(false)}
        />
      )}
    </div>
  )
}
