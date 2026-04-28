// PreparationsPage — Bases cuisinées (types + marmites actives)
// ADR-14 : portions_restantes lues directement depuis DB (¬ Redis)
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, ChevronDown, ChevronRight, X } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { normalizeError } from '@shared/errors/normalizer'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import type {
  IngredientRead,
  InstancePreparationRead,
  TypePreparationRead,
  RecetteLigneRead,
  IngredientStockRequis,
} from '@/types/restaurant-v2'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtHeure(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

function baseBadge(statut: 'dispo' | 'faible' | 'epuise'): { label: string; cls: string } {
  if (statut === 'dispo') return { label: 'Disponible', cls: 'bg-emerald-50 text-emerald-700' }
  if (statut === 'faible') return { label: 'Stock faible', cls: 'bg-amber-50 text-amber-700' }
  return { label: 'Épuisé', cls: 'bg-red-50 text-red-600' }
}

// ── BaseCard (instance marmite — horizontal) ──────────────────────────────────

function BaseCard({ m }: { m: InstancePreparationRead }) {
  const pct = m.pourcentage_restant
  const isWarn = m.statut_badge !== 'dispo'
  const fillColor = m.statut_badge === 'epuise'
    ? 'bg-red-500'
    : isWarn ? 'bg-amber-500' : 'bg-emerald-500'
  const valColor = isWarn ? 'text-amber-600' : 'text-stone-900'
  const badge = baseBadge(m.statut_badge)
  const borderCls = isWarn ? 'border-amber-200' : 'border-stone-200'

  const [showProteines, setShowProteines] = useState(false)

  return (
    <div className={`bg-white border ${borderCls} rounded-xl px-4 py-3.5 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow`}>
      <div className="min-w-[160px] shrink-0">
        <div className="text-[13px] font-semibold text-stone-900">{m.type_preparation_nom}</div>
        <div className="text-[10px] font-mono text-stone-400">ADR-14 · DB direct</div>
      </div>
      <div className="min-w-[90px] shrink-0 text-center">
        <div className={`text-[16px] font-bold tabular-nums tracking-tight ${valColor}`}>
          {m.portions_restantes}
          <span className="text-[13px] font-normal text-stone-400">/{m.portions_initiales}</span>
        </div>
        <div className="text-[11px] text-stone-400">portions</div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-center text-[11px] text-stone-500 mb-1">
          <span className={isWarn ? 'text-amber-600' : ''}>{pct}%</span>
          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${badge.cls}`}>{badge.label}</span>
        </div>
        <div className="h-[6px] bg-stone-200 rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${fillColor}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div className="min-w-[90px] shrink-0 text-[11px]">
        <span className="text-[10px] text-stone-400 block mb-0.5">Cuisiné à</span>
        <span className="text-stone-500">{fmtHeure(m.heure_lancement)}</span>
      </div>
      <div className="shrink-0 relative">
        <button
          onClick={() => setShowProteines(v => !v)}
          className="px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-stone-100 text-stone-600 border border-stone-200 hover:bg-stone-200 transition-colors"
        >
          Protéines
        </button>
        {showProteines && m.proteines_disponibles.length > 0 && (
          <div className="absolute right-0 top-full mt-1 z-30 bg-white border border-stone-200 rounded-xl shadow-lg p-2.5 min-w-[180px]">
            {m.proteines_disponibles.map(p => (
              <div key={p.ingredient_id} className="flex items-center justify-between gap-3 py-1 text-[11px]">
                <span className="text-stone-900 font-medium truncate">{p.nom}</span>
                <span className={`font-mono shrink-0 ${p.stock_badge === 'full' ? 'text-emerald-600' : p.stock_badge === 'low' ? 'text-amber-600' : 'text-red-500'}`}>
                  {p.stock_actuel_kg} {p.unite_stock}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── ModalBaseForm (Créer / Modifier TypePreparation) ──────────────────────────

function ModalBaseForm({
  base,
  onClose,
}: {
  base: TypePreparationRead | null
  onClose: () => void
}) {
  const qc = useQueryClient()
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  const isEdit = base !== null
  const [nom, setNom] = useState(base?.nom ?? '')
  const [portions, setPortions] = useState(String(base?.portions_par_batch ?? ''))
  const [notes, setNotes] = useState(base?.notes ?? '')
  const [error, setError] = useState<string | null>(null)

  const createMut = useMutation({
    mutationFn: () => restaurantApi.createTypePreparation({
      nom,
      portions_par_batch: parseInt(portions, 10),
      notes: notes || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-types-prep'] })
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const updateMut = useMutation({
    mutationFn: () => restaurantApi.updateTypePreparation(base!.id, {
      nom,
      portions_par_batch: parseInt(portions, 10),
      notes: notes || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-types-prep'] })
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const isPending = createMut.isPending || updateMut.isPending
  const canSubmit = nom.trim() !== '' && portions.trim() !== '' && !isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        className="bg-white rounded-2xl border border-stone-200 w-full max-w-md shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-100">
          <h2 className="text-[15px] font-bold text-stone-900">
            {isEdit ? 'Modifier la base' : 'Nouvelle base cuisinée'}
          </h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900 transition-colors" aria-label="Fermer">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4 flex flex-col gap-4">
          {error && (
            <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          <div>
            <label className="text-[12px] font-semibold text-stone-700 mb-1 block">Nom *</label>
            <input
              type="text"
              value={nom}
              onChange={e => setNom(e.target.value)}
              // eslint-disable-next-line jsx-a11y/no-autofocus
              autoFocus
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
              placeholder="Ex : Sauce bolognaise"
            />
          </div>

          <div>
            <label className="text-[12px] font-semibold text-stone-700 mb-1 block">Portions par batch *</label>
            <input
              type="number"
              min={1}
              value={portions}
              onChange={e => setPortions(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
              placeholder="20"
            />
          </div>

          <div>
            <label className="text-[12px] font-semibold text-stone-700 mb-1 block">Notes (optionnel)</label>
            <input
              type="text"
              value={notes}
              onChange={e => setNotes(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
              placeholder="Instructions, temps de cuisson…"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 px-5 py-4 border-t border-stone-100">
          <button onClick={onClose} className="px-4 py-2 text-[13px] text-stone-500 hover:text-stone-900 font-medium transition-colors">
            Annuler
          </button>
          <button
            onClick={() => isEdit ? updateMut.mutate() : createMut.mutate()}
            disabled={!canSubmit}
            className="px-4 py-2 text-[13px] font-semibold bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-40 transition-colors"
          >
            {isPending ? 'Enregistrement…' : isEdit ? 'Modifier' : 'Créer'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── ModalAddRecetteLigne ──────────────────────────────────────────────────────

function ModalAddRecetteLigne({
  typeId,
  ingredients,
  onClose,
}: {
  typeId: number
  ingredients: IngredientRead[]
  onClose: () => void
}) {
  const qc = useQueryClient()
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  const [ingredientId, setIngredientId] = useState('')
  const [quantite, setQuantite] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => restaurantApi.addRecetteLigne(typeId, {
      ingredient_id: parseInt(ingredientId, 10),
      quantite_par_batch: parseFloat(quantite),
      notes: notes || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-recette', typeId] })
      qc.invalidateQueries({ queryKey: ['restaurant-stock-requis', typeId] })
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const selectedIng = ingredients.find(i => i.id === Number(ingredientId))
  const canSubmit = ingredientId !== '' && quantite !== '' && !mutation.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        className="bg-white rounded-2xl border border-stone-200 w-full max-w-md shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-100">
          <h2 className="text-[15px] font-bold text-stone-900">Ajouter un ingrédient</h2>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900 transition-colors" aria-label="Fermer">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4 flex flex-col gap-4">
          {error && (
            <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          <div>
            <label className="text-[12px] font-semibold text-stone-700 mb-1 block">Ingrédient *</label>
            <select
              value={ingredientId}
              onChange={e => setIngredientId(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
            >
              <option value="">Sélectionner…</option>
              {ingredients.map(i => (
                <option key={i.id} value={String(i.id)}>{i.nom} ({i.unite_stock})</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-[12px] font-semibold text-stone-700 mb-1 block">
              Quantité par batch{selectedIng ? ` (${selectedIng.unite_stock})` : ''} *
            </label>
            <input
              type="number"
              min={0.001}
              step={0.1}
              value={quantite}
              onChange={e => setQuantite(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
              placeholder="0.5"
            />
          </div>

          <div>
            <label className="text-[12px] font-semibold text-stone-700 mb-1 block">Notes (optionnel)</label>
            <input
              type="text"
              value={notes}
              onChange={e => setNotes(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
              placeholder="Ex : mariner 30 min avant"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 px-5 py-4 border-t border-stone-100">
          <button onClick={onClose} className="px-4 py-2 text-[13px] text-stone-500 hover:text-stone-900 font-medium transition-colors">
            Annuler
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!canSubmit}
            className="px-4 py-2 text-[13px] font-semibold bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-40 transition-colors"
          >
            {mutation.isPending ? 'Ajout…' : 'Ajouter'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── TypePreparationCard ───────────────────────────────────────────────────────

function TypePreparationCard({
  tp,
  marmites,
  ingredients,
  onEdit,
  onDelete,
}: {
  tp: TypePreparationRead
  marmites: InstancePreparationRead[]
  ingredients: IngredientRead[]
  onEdit: (tp: TypePreparationRead) => void
  onDelete: (tp: TypePreparationRead) => void
}) {
  const qc = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const [mutError, setMutError] = useState('')
  const [showAddLigne, setShowAddLigne] = useState(false)
  const tpMarmites = marmites.filter(m => m.type_preparation_id === tp.id)

  const { data: recette, isLoading: recetteLoading } = useQuery({
    queryKey: ['restaurant-recette', tp.id],
    queryFn: () => restaurantApi.listRecette(tp.id),
    enabled: expanded,
    staleTime: 30_000,
  })

  const { data: stockRequis } = useQuery({
    queryKey: ['restaurant-stock-requis', tp.id],
    queryFn: () => restaurantApi.getStockRequis(tp.id),
    enabled: expanded,
    staleTime: 30_000,
  })

  const removeMut = useMutation({
    mutationFn: (ligneId: number) => restaurantApi.removeRecetteLigne(tp.id, ligneId),
    onSuccess: () => {
      setMutError('')
      qc.invalidateQueries({ queryKey: ['restaurant-recette', tp.id] })
      qc.invalidateQueries({ queryKey: ['restaurant-stock-requis', tp.id] })
    },
    onError: (err) => setMutError(normalizeError(err).message || 'Erreur retrait ingrédient'),
  })

  const stockMap = new Map<number, IngredientStockRequis>()
  if (stockRequis) {
    for (const ir of stockRequis.ingredients_requis) {
      stockMap.set(ir.ingredient_id, ir)
    }
  }

  return (
    <div className="border border-stone-200 rounded-xl overflow-hidden bg-white shadow-sm">
      {showAddLigne && (
        <ModalAddRecetteLigne
          typeId={tp.id}
          ingredients={ingredients}
          onClose={() => setShowAddLigne(false)}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-stone-50">
        <button
          onClick={() => setExpanded(v => !v)}
          className="flex items-center gap-2 text-left flex-1 min-w-0"
        >
          {expanded
            ? <ChevronDown className="h-3.5 w-3.5 text-stone-400 shrink-0" />
            : <ChevronRight className="h-3.5 w-3.5 text-stone-400 shrink-0" />
          }
          <span className="text-[13px] font-semibold text-stone-900">{tp.nom}</span>
          <span className="text-[11px] text-stone-400">{tp.portions_par_batch} portions/batch</span>
          {tp.notes && (
            <span className="text-[11px] text-stone-400 truncate">· {tp.notes}</span>
          )}
        </button>
        <div className="flex items-center gap-2 shrink-0">
          {tpMarmites.length > 0 ? (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">
              {tpMarmites.length} active{tpMarmites.length > 1 ? 's' : ''}
            </span>
          ) : (
            <span className="text-[11px] text-stone-400">0 marmite</span>
          )}
          <button onClick={() => onEdit(tp)} className="p-1 text-stone-400 hover:text-amber-600 transition-colors" title="Modifier">
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button onClick={() => onDelete(tp)} className="p-1 text-stone-400 hover:text-red-600 transition-colors" title="Supprimer">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {mutError && (
        <div className="mx-4 mt-2 px-3 py-2 bg-red-50 border border-red-100 rounded-lg text-[12px] text-red-600">
          {mutError}
        </div>
      )}

      {/* Contenu déplié */}
      {expanded && (
        <div className="border-t border-stone-200">
          <div className="flex">
            {/* Colonne gauche : recette + marmites */}
            <div className="flex-1 min-w-0">
              {/* Recette */}
              <div className="px-4 py-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[12px] font-semibold text-stone-900">Composition (recette)</span>
                  <button
                    onClick={() => setShowAddLigne(true)}
                    className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-amber-600 border border-amber-300 rounded-lg hover:bg-amber-50 transition-colors"
                  >
                    <Plus className="h-3 w-3" />
                    Ingrédient
                  </button>
                </div>

                {recetteLoading ? (
                  <div className="space-y-2">
                    {[1, 2, 3].map(i => (
                      <div key={i} className="h-8 bg-stone-200 rounded-lg animate-pulse" />
                    ))}
                  </div>
                ) : !recette || recette.length === 0 ? (
                  <p className="text-[12px] text-stone-400 py-2 text-center">
                    Aucun ingrédient — ajoutez la recette
                  </p>
                ) : (
                  <div className="border border-stone-200 rounded-xl overflow-hidden">
                    <table className="w-full text-left">
                      <thead className="bg-stone-50">
                        <tr>
                          <th className="px-3 py-1.5 text-[10px] font-semibold text-stone-500 uppercase">Ingrédient</th>
                          <th className="px-3 py-1.5 text-[10px] font-semibold text-stone-500 uppercase">Qté/batch</th>
                          <th className="px-3 py-1.5 text-[10px] font-semibold text-stone-500 uppercase">Stock</th>
                          <th className="px-3 py-1.5 text-[10px] font-semibold text-stone-500 uppercase w-8" />
                        </tr>
                      </thead>
                      <tbody>
                        {recette.map((ligne: RecetteLigneRead) => {
                          const sr = stockMap.get(ligne.ingredient_id)
                          const suffisant = sr?.suffisant ?? true
                          return (
                            <tr key={ligne.id} className="border-t border-stone-100">
                              <td className="px-3 py-2 text-[12px] font-medium text-stone-900">{ligne.nom}</td>
                              <td className="px-3 py-2 text-[12px] font-mono text-stone-900">
                                {ligne.quantite_par_batch} {ligne.unite}
                              </td>
                              <td className="px-3 py-2">
                                {sr ? (
                                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                                    suffisant
                                      ? 'bg-emerald-50 text-emerald-700'
                                      : 'bg-red-50 text-red-600'
                                  }`}>
                                    {sr.stock_actuel} {sr.unite} {suffisant ? '(OK)' : '(insuffisant)'}
                                  </span>
                                ) : (
                                  <span className="text-[11px] text-stone-400">—</span>
                                )}
                              </td>
                              <td className="px-3 py-2">
                                <button
                                  onClick={() => removeMut.mutate(ligne.id)}
                                  disabled={removeMut.isPending}
                                  className="text-stone-400 hover:text-red-600 transition-colors"
                                  title="Retirer"
                                >
                                  <X className="h-3.5 w-3.5" />
                                </button>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Marmites actives */}
              {tpMarmites.length > 0 && (
                <div className="px-4 pb-3">
                  <span className="text-[12px] font-semibold text-stone-900 block mb-2">Marmites actives</span>
                  <div className="flex flex-col gap-1">
                    {tpMarmites.map(m => <BaseCard key={m.instance_id} m={m} />)}
                  </div>
                </div>
              )}
            </div>

            {/* Colonne droite : illustration */}
            <div className="hidden md:flex w-[220px] shrink-0 border-l border-stone-200 items-center justify-center bg-stone-50 p-4">
              <img
                src="/images/base-cuisinee.svg"
                alt="Base cuisinée"
                className="w-full max-w-[180px] opacity-80"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── ConfirmDeleteModal ────────────────────────────────────────────────────────

function ConfirmDeleteModal({
  tp,
  onClose,
}: {
  tp: TypePreparationRead
  onClose: () => void
}) {
  const qc = useQueryClient()
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  const [error, setError] = useState<string | null>(null)

  const deleteMut = useMutation({
    mutationFn: () => restaurantApi.deleteTypePreparation(tp.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-types-prep'] })
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        className="bg-white rounded-2xl border border-stone-200 w-full max-w-sm shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-stone-100">
          <h2 className="text-[15px] font-bold text-stone-900">Supprimer la base</h2>
        </div>
        <div className="px-5 py-4">
          {error && (
            <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2 mb-3">{error}</p>
          )}
          <p className="text-[13px] text-stone-500">
            Supprimer <strong className="text-stone-900">{tp.nom}</strong> ?
            Cette action désactive la base (soft-delete).
          </p>
        </div>
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-stone-100">
          <button onClick={onClose} className="px-4 py-2 text-[13px] text-stone-500 hover:text-stone-900 font-medium transition-colors">
            Annuler
          </button>
          <button
            onClick={() => deleteMut.mutate()}
            disabled={deleteMut.isPending}
            className="px-4 py-2 text-[13px] font-semibold bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-40 transition-colors"
          >
            {deleteMut.isPending ? 'Suppression…' : 'Supprimer'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── PreparationsPage ──────────────────────────────────────────────────────────

export default function PreparationsPage() {
  const [showForm, setShowForm] = useState(false)
  const [editTarget, setEditTarget] = useState<TypePreparationRead | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<TypePreparationRead | null>(null)

  const { data: types, isLoading: typesLoading } = useQuery({
    queryKey: ['restaurant-types-prep'],
    queryFn: () => restaurantApi.listTypesPreparation(),
    staleTime: 30_000,
  })

  const { data: marmitesData } = useQuery({
    queryKey: ['restaurant-marmites'],
    queryFn: () => restaurantApi.getMarmites(),
    staleTime: 30_000,
  })

  const { data: ingData } = useQuery({
    queryKey: ['restaurant-ingredients-for-recette'],
    queryFn: () => restaurantApi.listIngredients({ per_page: 100 }),
    staleTime: 60_000,
  })

  const typesList = types ?? []
  const marmites = marmitesData?.items ?? []
  const ingredients = ingData?.items ?? []

  const marmitesActives = marmites.filter(m => m.statut_badge !== 'epuise')
  const marmitesEpuisees = marmites.filter(m => m.statut_badge === 'epuise')

  return (
    <div className="min-h-screen bg-stone-50">
      {/* Modals */}
      {showForm && (
        <ModalBaseForm
          base={editTarget}
          onClose={() => { setShowForm(false); setEditTarget(null) }}
        />
      )}
      {deleteTarget && (
        <ConfirmDeleteModal
          tp={deleteTarget}
          onClose={() => setDeleteTarget(null)}
        />
      )}

      {/* Sticky header */}
      <div className="sticky top-0 z-20 bg-white/95 backdrop-blur border-b border-stone-200 px-5 py-3">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-[17px] font-bold text-stone-900 tracking-tight shrink-0">Préparations</h1>
          {marmitesActives.length > 0 && (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">
              {marmitesActives.length} marmite{marmitesActives.length > 1 ? 's' : ''} active{marmitesActives.length > 1 ? 's' : ''}
            </span>
          )}
          {marmitesEpuisees.length > 0 && (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-red-50 text-red-600">
              {marmitesEpuisees.length} épuisée{marmitesEpuisees.length > 1 ? 's' : ''}
            </span>
          )}
          <button
            onClick={() => { setEditTarget(null); setShowForm(true) }}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 text-white text-[12px] font-semibold rounded-lg hover:bg-amber-700 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Nouvelle base
          </button>
        </div>
      </div>

      <div className="px-5 py-4 space-y-8">
        {/* Marmites actives (snapshot temps réel) */}
        {marmites.length > 0 && (
          <section>
            <h2 className="text-[13px] font-semibold text-stone-900 mb-3">
              Marmites en service
              <span className="ml-2 text-[11px] font-normal text-stone-400">ADR-14 · rafraîchi à chaque render</span>
            </h2>
            <div className="flex flex-col gap-2">
              {marmites.map(m => <BaseCard key={m.instance_id} m={m} />)}
            </div>
          </section>
        )}

        {/* Liste des types de préparation */}
        <section>
          <h2 className="text-[13px] font-semibold text-stone-900 mb-3">
            Bases cuisinées ({typesList.length})
          </h2>

          {typesLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-12 bg-stone-200 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : typesList.length === 0 ? (
            <div className="py-16 text-center">
              <p className="text-[13px] text-stone-400 mb-3">Aucune base cuisinée définie.</p>
              <button
                onClick={() => { setEditTarget(null); setShowForm(true) }}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-amber-600 text-white text-[13px] font-semibold rounded-lg hover:bg-amber-700 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Créer la première base
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {typesList.map(tp => (
                <TypePreparationCard
                  key={tp.id}
                  tp={tp}
                  marmites={marmites}
                  ingredients={ingredients}
                  onEdit={(t) => { setEditTarget(t); setShowForm(true) }}
                  onDelete={setDeleteTarget}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
