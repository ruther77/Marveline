// Section "Produits épicerie sources" dans la fiche ingrédient.
// Affiche la liste ordonnée des produits épicerie liés à cet ingrédient,
// avec facteur de conversion, réordonnancement ↑↓ et suppression.
// Permet d'ajouter de nouveaux produits via recherche autocomplete.

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Plus, Search, Trash2, X } from 'lucide-react'
import { ingredientSourcingApi } from '@/api/ingredient_sourcing'
import { normalizeError } from '@shared/errors/normalizer'
import type {
  MappingWithProduit,
  ProduitEpicerieSearchItem,
} from '@/types/ingredient_sourcing'

interface Props {
  ingredientId: number
  ingredientUnite: string // kg, L, pièce...
}

export function IngredientSourcingSection({ ingredientId, ingredientUnite }: Props) {
  const qc = useQueryClient()
  const queryKey = ['ingredient-mappings', ingredientId]

  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => ingredientSourcingApi.listMappings(ingredientId),
  })

  const mappings = data?.items ?? []

  const deleteMut = useMutation({
    mutationFn: (produitId: number) =>
      ingredientSourcingApi.deleteMapping(ingredientId, produitId),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })

  const updateMut = useMutation({
    mutationFn: (args: { produitId: number; facteur_conv: string }) =>
      ingredientSourcingApi.updateMapping(ingredientId, args.produitId, {
        facteur_conv: args.facteur_conv,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })

  const reorderMut = useMutation({
    mutationFn: (items: { produit_id: number; ordre: number }[]) =>
      ingredientSourcingApi.reorderMappings(ingredientId, { items }),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  })

  const moveUp = (index: number) => {
    if (index === 0) return
    const newOrder = mappings.map((m, i) => {
      if (i === index - 1) return { produit_id: m.produit_id, ordre: m.ordre + 1 }
      if (i === index) return { produit_id: m.produit_id, ordre: m.ordre - 1 }
      return { produit_id: m.produit_id, ordre: m.ordre }
    })
    // Normaliser les ordres pour rester séquentiels
    const sorted = [...newOrder].sort((a, b) => a.ordre - b.ordre)
    reorderMut.mutate(sorted.map((m, i) => ({ produit_id: m.produit_id, ordre: i })))
  }

  const moveDown = (index: number) => {
    if (index >= mappings.length - 1) return
    moveUp(index + 1)
  }

  return (
    <div className="border-t border-stone-100 pt-4 mt-2">
      <div className="flex items-baseline justify-between mb-3">
        <label className="text-[12px] font-bold text-stone-800">
          Produits épicerie sources
          <span className="ml-2 text-[11px] font-normal text-stone-400">
            (ordre de préférence pour réapprovisionnement)
          </span>
        </label>
      </div>

      {isLoading && (
        <div className="text-[12px] text-stone-400 italic px-1">Chargement…</div>
      )}
      {error && (
        <div className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2 mb-2">
          {normalizeError(error).message}
        </div>
      )}

      {!isLoading && mappings.length === 0 && (
        <div className="text-[12px] text-stone-500 bg-stone-50 rounded-lg px-3 py-3 mb-3 border border-dashed border-stone-200">
          Aucun produit épicerie lié. Ajoutez-en un ci-dessous pour activer le
          réapprovisionnement automatique.
        </div>
      )}

      {mappings.length > 0 && (
        <ul className="flex flex-col gap-1.5 mb-3">
          {mappings.map((m, idx) => (
            <MappingLine
              key={m.id}
              mapping={m}
              ingredientUnite={ingredientUnite}
              isFirst={idx === 0}
              isLast={idx === mappings.length - 1}
              onMoveUp={() => moveUp(idx)}
              onMoveDown={() => moveDown(idx)}
              onDelete={() => deleteMut.mutate(m.produit_id)}
              onFacteurChange={(value) =>
                updateMut.mutate({ produitId: m.produit_id, facteur_conv: value })
              }
              busy={deleteMut.isPending || updateMut.isPending || reorderMut.isPending}
            />
          ))}
        </ul>
      )}

      <AddMappingPicker
        ingredientId={ingredientId}
        existingProduitIds={new Set(mappings.map((m) => m.produit_id))}
        nextOrdre={mappings.length}
        onAdded={() => qc.invalidateQueries({ queryKey })}
      />
    </div>
  )
}

// ── Ligne mapping (display + edit facteur + reorder + delete) ────────────────

function MappingLine({
  mapping,
  ingredientUnite,
  isFirst,
  isLast,
  onMoveUp,
  onMoveDown,
  onDelete,
  onFacteurChange,
  busy,
}: {
  mapping: MappingWithProduit
  ingredientUnite: string
  isFirst: boolean
  isLast: boolean
  onMoveUp: () => void
  onMoveDown: () => void
  onDelete: () => void
  onFacteurChange: (v: string) => void
  busy: boolean
}) {
  const [facteur, setFacteur] = useState(mapping.facteur_conv)
  useEffect(() => setFacteur(mapping.facteur_conv), [mapping.facteur_conv])

  const dirty = facteur !== mapping.facteur_conv
  const stockDispo = parseFloat(mapping.produit_stock_disponible) || 0
  const stockCouverture =
    stockDispo * (parseFloat(mapping.facteur_conv) || 1)

  return (
    <li className="flex items-center gap-2 bg-stone-50 border border-stone-200 rounded-lg px-2 py-1.5">
      {/* Reorder handles */}
      <div className="flex flex-col">
        <button
          type="button"
          onClick={onMoveUp}
          disabled={isFirst || busy}
          className="p-0.5 text-stone-400 hover:text-stone-700 disabled:opacity-30"
          aria-label="Monter"
        >
          <ArrowUp className="h-3 w-3" />
        </button>
        <button
          type="button"
          onClick={onMoveDown}
          disabled={isLast || busy}
          className="p-0.5 text-stone-400 hover:text-stone-700 disabled:opacity-30"
          aria-label="Descendre"
        >
          <ArrowDown className="h-3 w-3" />
        </button>
      </div>

      {/* Badge ordre */}
      <span className="text-[10px] font-bold text-amber-700 bg-amber-100 rounded px-1.5 py-0.5 w-6 text-center">
        #{mapping.ordre + 1}
      </span>

      {/* Désignation produit + stock */}
      <div className="flex-1 min-w-0">
        <div className="text-[12px] font-medium text-stone-800 truncate">
          {mapping.produit_designation}
        </div>
        <div className="text-[10px] text-stone-500">
          Stock {stockDispo} {mapping.produit_unite_vente} → ≈{' '}
          {stockCouverture.toFixed(2)} {ingredientUnite}
        </div>
      </div>

      {/* Facteur de conversion */}
      <div className="flex items-center gap-1">
        <label className="text-[10px] text-stone-500">×</label>
        <input
          type="number"
          step="0.0001"
          min="0.0001"
          value={facteur}
          onChange={(e) => setFacteur(e.target.value)}
          onBlur={() => {
            if (dirty && parseFloat(facteur) > 0) onFacteurChange(facteur)
          }}
          className="w-16 bg-white border border-stone-200 rounded px-1.5 py-1 text-[11px] text-right text-stone-900 focus:outline-none focus:border-amber-400"
          title={`Facteur de conversion : 1 ${mapping.produit_unite_vente} = facteur × ${ingredientUnite}`}
        />
        <span className="text-[10px] text-stone-400">{ingredientUnite}/{mapping.produit_unite_vente}</span>
      </div>

      {/* Delete */}
      <button
        type="button"
        onClick={onDelete}
        disabled={busy}
        className="p-1 text-stone-400 hover:text-red-600 disabled:opacity-30"
        aria-label="Supprimer"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </li>
  )
}

// ── Picker pour ajouter un produit ──────────────────────────────────────────

function AddMappingPicker({
  ingredientId,
  existingProduitIds,
  nextOrdre,
  onAdded,
}: {
  ingredientId: number
  existingProduitIds: Set<number>
  nextOrdre: number
  onAdded: () => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<ProduitEpicerieSearchItem | null>(null)
  const [facteur, setFacteur] = useState('1')
  const [error, setError] = useState<string | null>(null)

  const debouncedQ = useDebouncedValue(search, 250)

  const searchQuery = useQuery({
    queryKey: ['sourcing-search', debouncedQ],
    queryFn: () =>
      debouncedQ.length >= 2
        ? ingredientSourcingApi.searchProduitsEpicerie(debouncedQ)
        : Promise.resolve({ items: [] }),
    enabled: open && debouncedQ.length >= 2,
  })

  const addMut = useMutation({
    mutationFn: () =>
      ingredientSourcingApi.addMapping(ingredientId, {
        produit_id: selected!.id,
        ordre: nextOrdre,
        facteur_conv: facteur,
      }),
    onSuccess: () => {
      onAdded()
      setSelected(null)
      setSearch('')
      setFacteur('1')
      setOpen(false)
      setError(null)
    },
    onError: (err) => setError(normalizeError(err).message),
  })

  const filteredItems = useMemo(
    () =>
      (searchQuery.data?.items ?? []).filter((p) => !existingProduitIds.has(p.id)),
    [searchQuery.data, existingProduitIds],
  )

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 text-[12px] font-medium text-amber-700 hover:text-amber-900"
      >
        <Plus className="h-3.5 w-3.5" />
        Ajouter un produit épicerie
      </button>
    )
  }

  return (
    <div className="bg-white border border-stone-200 rounded-lg p-3 flex flex-col gap-2">
      {error && (
        <div className="text-[12px] text-red-600 bg-red-50 rounded px-2 py-1">
          {error}
        </div>
      )}

      {/* Search input */}
      <div className="flex items-center gap-2">
        <div className="flex-1 flex items-center gap-2 bg-stone-50 border border-stone-200 rounded-lg px-2.5 py-1.5">
          <Search className="h-3.5 w-3.5 text-stone-400" />
          <input
            type="text"
            autoFocus
            placeholder="Rechercher un produit épicerie (min 2 car.)"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setSelected(null)
            }}
            className="flex-1 bg-transparent text-[12px] text-stone-900 focus:outline-none"
          />
        </div>
        <button
          type="button"
          onClick={() => {
            setOpen(false)
            setSearch('')
            setSelected(null)
            setError(null)
          }}
          className="p-1 text-stone-400 hover:text-stone-900"
          aria-label="Fermer"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Dropdown résultats */}
      {!selected && debouncedQ.length >= 2 && (
        <div className="max-h-40 overflow-y-auto bg-white border border-stone-100 rounded">
          {searchQuery.isLoading && (
            <div className="text-[11px] text-stone-400 italic px-2 py-1.5">
              Recherche…
            </div>
          )}
          {!searchQuery.isLoading && filteredItems.length === 0 && (
            <div className="text-[11px] text-stone-400 italic px-2 py-1.5">
              Aucun produit trouvé
            </div>
          )}
          {filteredItems.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setSelected(p)}
              className="w-full text-left px-2 py-1.5 hover:bg-amber-50 border-b border-stone-50 last:border-b-0"
            >
              <div className="text-[12px] font-medium text-stone-800 truncate">
                {p.designation_clean}
              </div>
              <div className="text-[10px] text-stone-500">
                {p.ean ? `EAN ${p.ean} · ` : ''}
                {p.unite_vente} · stock {p.stock_disponible}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Produit sélectionné + facteur */}
      {selected && (
        <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
          <div className="flex-1 min-w-0">
            <div className="text-[12px] font-medium text-stone-800 truncate">
              {selected.designation_clean}
            </div>
            <div className="text-[10px] text-stone-500">
              Unité vente : {selected.unite_vente}
            </div>
          </div>
          <label className="text-[10px] text-stone-500">×</label>
          <input
            type="number"
            step="0.0001"
            min="0.0001"
            value={facteur}
            onChange={(e) => setFacteur(e.target.value)}
            className="w-16 bg-white border border-stone-200 rounded px-1.5 py-1 text-[11px] text-right text-stone-900 focus:outline-none focus:border-amber-400"
          />
          <button
            type="button"
            onClick={() => addMut.mutate()}
            disabled={addMut.isPending || parseFloat(facteur) <= 0}
            className="text-[11px] font-semibold bg-amber-600 text-white rounded px-2.5 py-1 hover:bg-amber-700 disabled:opacity-50"
          >
            {addMut.isPending ? '…' : 'Ajouter'}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Hook debounce minimaliste (évite dépendance externe) ─────────────────────

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(t)
  }, [value, delay])
  return debounced
}
