// CataloguePage — CRUD ingrédients + catégories
// Admin : création, modification, suppression (soft pour ingrédients)
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, X } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { IngredientSourcingSection } from '@/components/IngredientSourcingSection'
import { normalizeError } from '@shared/errors/normalizer'
import { useToast } from '@shared/components/ui/Toast'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import type {
  IngredientRead,
  CategorieIngredientRead,
  IngredientCreateBody,
  IngredientUpdateBody,
  CategorieIngredientCreateBody,
  CategorieIngredientUpdateBody,
} from '@/types/restaurant-v2'

// ── Types ─────────────────────────────────────────────────────────────────────

type TabActive = 'ingredients' | 'categories'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtPrix(cts: number): string {
  return (cts / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

// ── IngForm (create / edit ingrédient) ────────────────────────────────────────

function IngForm({
  ing,
  categories,
  onClose,
}: {
  ing: IngredientRead | null
  categories: CategorieIngredientRead[]
  onClose: () => void
}) {
  const qc = useQueryClient()
  const toast = useToast()
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  const isEdit = ing !== null

  const [nom, setNom] = useState(ing?.nom ?? '')
  const [unite, setUnite] = useState(ing?.unite_stock ?? '')
  const [catId, setCatId] = useState<string>(ing?.categorie_id ? String(ing.categorie_id) : '')
  const [stockAlerte, setStockAlerte] = useState(ing ? String(ing.stock_alerte) : '0')
  const [coutEuros, setCoutEuros] = useState(ing ? String(ing.cout_unitaire_cts / 100) : '0')
  const [error, setError] = useState<string | null>(null)

  const createMut = useMutation({
    mutationFn: () => {
      const body: IngredientCreateBody = {
        nom: nom.trim(),
        unite_stock: unite.trim(),
        categorie_id: catId ? Number(catId) : null,
        stock_alerte: parseFloat(stockAlerte) || 0,
        cout_unitaire_cts: Math.round(parseFloat(coutEuros) * 100) || 0,
      }
      return restaurantApi.createIngredient(body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-ingredients'] })
      toast.success('Ingrédient créé', nom.trim())
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message),
  })

  const updateMut = useMutation({
    mutationFn: () => {
      const body: IngredientUpdateBody = {
        nom: nom.trim(),
        unite_stock: unite.trim(),
        categorie_id: catId ? Number(catId) : null,
        stock_alerte: parseFloat(stockAlerte) || 0,
        cout_unitaire_cts: Math.round(parseFloat(coutEuros) * 100) || 0,
      }
      return restaurantApi.updateIngredient(ing!.id, body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-ingredients'] })
      toast.success('Ingrédient mis à jour', nom.trim())
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message),
  })

  const isPending = createMut.isPending || updateMut.isPending
  const canSubmit = nom.trim() && unite.trim() && !isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div
        ref={trapRef} role="dialog" aria-modal="true"
        className={`bg-white rounded-2xl border border-stone-200 w-full shadow-xl max-h-[90vh] overflow-y-auto ${isEdit ? 'max-w-2xl' : 'max-w-md'}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-100">
          <h2 className="text-[15px] font-bold text-stone-900">
            {isEdit ? `Modifier — ${ing.nom}` : 'Nouvel ingrédient'}
          </h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900 transition-colors" aria-label="Fermer">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4 flex flex-col gap-3">
          {error && <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-stone-700 mb-1 block">Nom *</label>
              <input
                type="text" value={nom} onChange={(e) => setNom(e.target.value)} autoFocus
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
                placeholder="Ex: Tomate"
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold text-stone-700 mb-1 block">Unité *</label>
              <input
                type="text" value={unite} onChange={(e) => setUnite(e.target.value)}
                list="unites-list"
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
                placeholder="kg, L, unité…"
              />
              <datalist id="unites-list">
                {['kg', 'g', 'L', 'cl', 'unité', 'portion', 'boîte', 'sachet'].map((u) => (
                  <option key={u} value={u} />
                ))}
              </datalist>
            </div>
          </div>

          <div>
            <label className="text-[11px] font-semibold text-stone-700 mb-1 block">Catégorie</label>
            <select
              value={catId}
              onChange={(e) => setCatId(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
            >
              <option value="">— Aucune catégorie —</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.nom}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-stone-700 mb-1 block">Seuil alerte</label>
              <input
                type="number" min={0} step={0.1} value={stockAlerte}
                onChange={(e) => setStockAlerte(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold text-stone-700 mb-1 block">Coût unitaire (€)</label>
              <input
                type="number" min={0} step={0.01} value={coutEuros}
                onChange={(e) => setCoutEuros(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
              />
            </div>
          </div>

          {isEdit && ing && (
            <IngredientSourcingSection
              ingredientId={ing.id}
              ingredientUnite={unite.trim() || ing.unite_stock || ''}
            />
          )}
        </div>

        <div className="flex justify-end gap-2 px-5 py-4 border-t border-stone-100">
          <button onClick={onClose} className="px-4 py-2 text-[13px] text-stone-500 hover:text-stone-900 font-medium transition-colors">
            Annuler
          </button>
          <button
            onClick={() => isEdit ? updateMut.mutate() : createMut.mutate()}
            disabled={!canSubmit}
            className="px-4 py-2 text-[13px] font-semibold bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 transition-colors"
          >
            {isPending ? 'Enregistrement…' : isEdit ? 'Mettre à jour' : 'Créer'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── CatForm (create / edit catégorie) ─────────────────────────────────────────

function CatForm({
  cat,
  onClose,
}: {
  cat: CategorieIngredientRead | null
  onClose: () => void
}) {
  const qc = useQueryClient()
  const toast = useToast()
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  const isEdit = cat !== null

  const [nom, setNom] = useState(cat?.nom ?? '')
  const [isProteine, setIsProteine] = useState(cat?.is_proteine ?? false)
  const [error, setError] = useState<string | null>(null)

  const createMut = useMutation({
    mutationFn: () => {
      const body: CategorieIngredientCreateBody = { nom: nom.trim(), is_proteine: isProteine }
      return restaurantApi.createCategorieIngredient(body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-categories-ingredient'] })
      toast.success('Catégorie créée', nom.trim())
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message),
  })

  const updateMut = useMutation({
    mutationFn: () => {
      const body: CategorieIngredientUpdateBody = { nom: nom.trim(), is_proteine: isProteine }
      return restaurantApi.updateCategorieIngredient(cat!.id, body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-categories-ingredient'] })
      toast.success('Catégorie mise à jour', nom.trim())
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message),
  })

  const isPending = createMut.isPending || updateMut.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div
        ref={trapRef} role="dialog" aria-modal="true"
        className="bg-white rounded-2xl border border-stone-200 w-full max-w-sm shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-100">
          <h2 className="text-[15px] font-bold text-stone-900">
            {isEdit ? `Modifier — ${cat.nom}` : 'Nouvelle catégorie'}
          </h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900 transition-colors" aria-label="Fermer">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4 flex flex-col gap-3">
          {error && <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <div>
            <label className="text-[11px] font-semibold text-stone-700 mb-1 block">Nom *</label>
            <input
              type="text" value={nom} onChange={(e) => setNom(e.target.value)} autoFocus
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
              placeholder="Ex: Légumes"
            />
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox" checked={isProteine}
              onChange={(e) => setIsProteine(e.target.checked)}
              className="w-4 h-4 accent-amber-600"
            />
            <span className="text-[13px] text-stone-900">Catégorie protéine</span>
          </label>
        </div>

        <div className="flex justify-end gap-2 px-5 py-4 border-t border-stone-100">
          <button onClick={onClose} className="px-4 py-2 text-[13px] text-stone-500 hover:text-stone-900 font-medium transition-colors">
            Annuler
          </button>
          <button
            onClick={() => isEdit ? updateMut.mutate() : createMut.mutate()}
            disabled={!nom.trim() || isPending}
            className="px-4 py-2 text-[13px] font-semibold bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 transition-colors"
          >
            {isPending ? 'Enregistrement…' : isEdit ? 'Mettre à jour' : 'Créer'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Tab Ingrédients ───────────────────────────────────────────────────────────

function TabIngredients({ categories }: { categories: CategorieIngredientRead[] }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [formIng, setFormIng] = useState<IngredientRead | null | undefined>(undefined)

  const { data, isLoading } = useQuery({
    queryKey: ['restaurant-ingredients-catalogue'],
    queryFn: () => restaurantApi.listIngredients({ per_page: 100 }),
    staleTime: 30_000,
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => restaurantApi.deleteIngredient(id),
    onSuccess: (_d, id) => {
      qc.invalidateQueries({ queryKey: ['restaurant-ingredients-catalogue'] })
      qc.invalidateQueries({ queryKey: ['restaurant-ingredients'] })
      toast.success('Ingrédient supprimé')
      void id
    },
    onError: (err) => toast.error('Erreur', normalizeError(err).message),
  })

  const items = data?.items ?? []

  return (
    <>
      {formIng !== undefined && (
        <IngForm ing={formIng} categories={categories} onClose={() => setFormIng(undefined)} />
      )}

      <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200">
        <span className="text-[12px] text-stone-500">{items.length} ingrédient{items.length !== 1 ? 's' : ''}</span>
        <button
          onClick={() => setFormIng(null)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 text-white text-[12px] font-semibold rounded-lg hover:bg-amber-700 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Nouvel ingrédient
        </button>
      </div>

      {isLoading ? (
        <div className="pt-3 px-3 pb-3 space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-10 bg-stone-200 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="py-12 text-center text-stone-400 text-[13px]">
          Aucun ingrédient. Créez-en un.
        </div>
      ) : (
        <div className="bg-white mx-3 my-3 rounded-xl border border-stone-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-stone-50">
                <tr>
                  <th className="px-4 py-2 text-[10px] font-semibold text-stone-500 uppercase tracking-wide">Ingrédient</th>
                  <th className="px-4 py-2 text-[10px] font-semibold text-stone-500 uppercase tracking-wide">Unité</th>
                  <th className="px-4 py-2 text-[10px] font-semibold text-stone-500 uppercase tracking-wide">Catégorie</th>
                  <th className="px-4 py-2 text-[10px] font-semibold text-stone-500 uppercase tracking-wide">Seuil</th>
                  <th className="px-4 py-2 text-[10px] font-semibold text-stone-500 uppercase tracking-wide">Coût/u</th>
                  <th className="px-4 py-2 w-20" />
                </tr>
              </thead>
              <tbody>
                {items.map((ing) => (
                  <tr key={ing.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50 transition-colors">
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2.5">
                        {ing.image_url
                          ? <img src={ing.image_url} alt={ing.nom} className="w-7 h-7 rounded-md object-cover shrink-0" loading="lazy" />
                          : <div className="w-7 h-7 rounded-md bg-stone-100 shrink-0" />
                        }
                        <span className="text-[13px] font-medium text-stone-900">{ing.nom}</span>
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-[12px] font-mono text-stone-500">{ing.unite_stock}</td>
                    <td className="px-4 py-2.5 text-[12px] text-stone-500">{ing.categorie ?? '—'}</td>
                    <td className="px-4 py-2.5 text-[12px] font-mono text-stone-500">{ing.stock_alerte}</td>
                    <td className="px-4 py-2.5 text-[12px] text-stone-500">
                      {ing.cout_unitaire_cts > 0 ? fmtPrix(ing.cout_unitaire_cts) : '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2 justify-end">
                        <button
                          onClick={() => setFormIng(ing)}
                          className="p-1 text-stone-400 hover:text-amber-600 transition-colors"
                          title="Modifier"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => {
                            if (confirm(`Supprimer "${ing.nom}" ?`)) deleteMut.mutate(ing.id)
                          }}
                          disabled={deleteMut.isPending}
                          className="p-1 text-stone-400 hover:text-red-600 disabled:opacity-40 transition-colors"
                          title="Supprimer"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}

// ── Tab Catégories ────────────────────────────────────────────────────────────

function TabCategories() {
  const qc = useQueryClient()
  const toast = useToast()
  const [formCat, setFormCat] = useState<CategorieIngredientRead | null | undefined>(undefined)

  const { data: categories, isLoading } = useQuery({
    queryKey: ['restaurant-categories-ingredient'],
    queryFn: () => restaurantApi.listCategoriesIngredient(),
    staleTime: 60_000,
  })

  const deleteMut = useMutation({
    mutationFn: async (cat: CategorieIngredientRead) => {
      const { count } = await restaurantApi.getCategorieUsages(cat.id)
      if (count > 0) {
        throw new Error(`Cette catégorie est utilisée par ${count} ingrédient${count > 1 ? 's' : ''}. Réassignez-les d'abord.`)
      }
      return restaurantApi.deleteCategorieIngredient(cat.id)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-categories-ingredient'] })
      qc.invalidateQueries({ queryKey: ['restaurant-ingredients'] })
      toast.success('Catégorie supprimée')
    },
    onError: (err) => toast.error('Impossible de supprimer', normalizeError(err).message),
  })

  const items = categories ?? []

  return (
    <>
      {formCat !== undefined && (
        <CatForm cat={formCat} onClose={() => setFormCat(undefined)} />
      )}

      <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200">
        <span className="text-[12px] text-stone-500">{items.length} catégorie{items.length !== 1 ? 's' : ''}</span>
        <button
          onClick={() => setFormCat(null)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 text-white text-[12px] font-semibold rounded-lg hover:bg-amber-700 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Nouvelle catégorie
        </button>
      </div>

      {isLoading ? (
        <div className="pt-3 px-3 pb-3 space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-10 bg-stone-200 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="py-12 text-center text-stone-400 text-[13px]">
          Aucune catégorie. Créez-en une.
        </div>
      ) : (
        <div className="bg-white mx-3 my-3 rounded-xl border border-stone-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-stone-50">
                <tr>
                  <th className="px-4 py-2 text-[10px] font-semibold text-stone-500 uppercase tracking-wide">Catégorie</th>
                  <th className="px-4 py-2 text-[10px] font-semibold text-stone-500 uppercase tracking-wide">Type</th>
                  <th className="px-4 py-2 w-20" />
                </tr>
              </thead>
              <tbody>
                {items.map((cat) => (
                  <tr key={cat.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50 transition-colors">
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2.5">
                        {cat.image_url
                          ? <img src={cat.image_url} alt={cat.nom} className="w-7 h-7 rounded-md object-cover shrink-0" loading="lazy" />
                          : <div className="w-7 h-7 rounded-md bg-stone-100 shrink-0" />
                        }
                        <span className="text-[13px] font-medium text-stone-900">{cat.nom}</span>
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      {cat.is_proteine && (
                        <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-600">
                          Protéine
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2 justify-end">
                        <button
                          onClick={() => setFormCat(cat)}
                          className="p-1 text-stone-400 hover:text-amber-600 transition-colors"
                          title="Modifier"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => {
                            if (confirm(`Supprimer la catégorie "${cat.nom}" ?`)) deleteMut.mutate(cat)
                          }}
                          disabled={deleteMut.isPending}
                          className="p-1 text-stone-400 hover:text-red-600 disabled:opacity-40 transition-colors"
                          title="Supprimer"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}

// ── CataloguePage ─────────────────────────────────────────────────────────────

const TABS: { key: TabActive; label: string }[] = [
  { key: 'ingredients', label: 'Ingrédients' },
  { key: 'categories', label: 'Catégories' },
]

export default function CataloguePage() {
  const [activeTab, setActiveTab] = useState<TabActive>('ingredients')

  const { data: categories } = useQuery({
    queryKey: ['restaurant-categories-ingredient'],
    queryFn: () => restaurantApi.listCategoriesIngredient(),
    staleTime: 60_000,
  })

  return (
    <div className="min-h-screen bg-stone-50">
      {/* Header */}
      <div className="sticky top-0 z-20 bg-white/95 backdrop-blur border-b border-stone-200 px-5 py-3">
        <div className="flex items-center gap-4">
          <h1 className="text-[17px] font-bold text-stone-900 tracking-tight">Catalogue</h1>
          <div className="flex gap-1">
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-colors ${
                  activeTab === key
                    ? 'bg-amber-600 text-white'
                    : 'text-stone-600 hover:text-stone-900 hover:bg-stone-100'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {activeTab === 'ingredients' && (
        <TabIngredients categories={categories ?? []} />
      )}
      {activeTab === 'categories' && (
        <TabCategories />
      )}
    </div>
  )
}
