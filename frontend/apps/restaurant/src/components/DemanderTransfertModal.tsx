// Modale "Demander à l'épicerie" — refonte 2026-04-21
// Les lignes pointent maintenant sur des ingrédients restaurant (FK). Pour
// chaque ligne, une preview temps réel du résolveur cascade affiche les
// produits épicerie source + flag de déficit — avant envoi.
// Fallback "ingrédient libre" conservé pour lignes non mappées (texte pur).

import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import {
  AlertTriangle,
  CheckCircle,
  Plus,
  Search,
  Send,
  Trash2,
  X,
} from 'lucide-react'
import { ingredientSourcingApi } from '@/api/ingredient_sourcing'
import { restaurantApi } from '@/api/restaurant'
import { normalizeError } from '@shared/errors/normalizer'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import type { IngredientRead } from '@/types/restaurant-v2'
import type { ResolveResponse } from '@/types/ingredient_sourcing'

interface LigneDemande {
  /** Si renseigné : ligne résolvable par le backend. Sinon : texte libre. */
  ingredient_id: number | null
  ingredient_nom: string
  unit: string
  quantity: string
  notes: string
}

const EMPTY_LIGNE: LigneDemande = {
  ingredient_id: null,
  ingredient_nom: '',
  unit: 'kg',
  quantity: '',
  notes: '',
}

interface Props {
  epicerieTenantId: number
  onClose: () => void
}

export default function DemanderTransfertModal({ epicerieTenantId, onClose }: Props) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)

  const [notes, setNotes] = useState('')
  const [lignes, setLignes] = useState<LigneDemande[]>([{ ...EMPTY_LIGNE }])
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  // ── Ingrédients restaurant (pour le picker) ─────────────────────────────
  const ingredientsQ = useQuery({
    queryKey: ['restaurant-ingredients', 'all'],
    queryFn: () =>
      restaurantApi.listIngredients({ per_page: 500 }).then((r) => r.items),
  })
  const ingredients = ingredientsQ.data ?? []

  const mutation = useMutation({
    mutationFn: () =>
      restaurantApi.demanderTransfert({
        target_tenant_id: epicerieTenantId,
        notes: notes.trim() || null,
        lignes: lignes
          .filter((l) => l.ingredient_nom.trim() && Number(l.quantity) > 0)
          .map((l) => ({
            designation: l.ingredient_nom.trim(),
            quantity: Number(l.quantity),
            unit: l.unit,
            ingredient_restaurant_id: l.ingredient_id,
            notes: l.notes.trim() || null,
          })),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-transfer-requests'] })
      setSent(true)
    },
    onError: (err) =>
      setError(normalizeError(err).message || 'Erreur création demande'),
  })

  const lignesValides = lignes.filter(
    (l) => l.ingredient_nom.trim() && Number(l.quantity) > 0,
  )
  const canSubmit = lignesValides.length > 0 && epicerieTenantId > 0 && !mutation.isPending

  function updateLigne(i: number, patch: Partial<LigneDemande>) {
    setLignes((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  }

  function addLigne() {
    setLignes((prev) => [...prev, { ...EMPTY_LIGNE }])
  }

  function removeLigne(i: number) {
    setLignes((prev) =>
      prev.length === 1 ? [{ ...EMPTY_LIGNE }] : prev.filter((_, idx) => idx !== i),
    )
  }

  if (sent) {
    return (
      <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40">
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Demande envoyée"
          className="bg-white border border-stone-200 w-full sm:max-w-md flex flex-col items-center gap-5 shadow-xl rounded-t-2xl sm:rounded-2xl px-7 py-8 pb-[calc(env(safe-area-inset-bottom)+2rem)] sm:pb-8"
        >
          <div className="w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center">
            <CheckCircle className="h-7 w-7 text-emerald-600" />
          </div>
          <div className="text-center">
            <p className="text-[16px] font-bold text-stone-900">
              Demande envoyée à l'épicerie
            </p>
            <p className="text-[13px] text-stone-500 mt-1">
              Vous serez notifié quand elle sera traitée.
            </p>
          </div>
          <div className="flex flex-col gap-2 w-full">
            <button
              onClick={() => {
                onClose()
                navigate({ to: '/mes-demandes' })
              }}
              className="w-full h-12 bg-amber-600 text-white text-[14px] font-semibold rounded-xl hover:bg-amber-700 transition-colors"
            >
              Voir mes demandes
            </button>
            <button
              onClick={onClose}
              className="w-full h-11 text-[13px] text-stone-500 hover:text-stone-700"
            >
              Fermer
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40">
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="demander-transfert-title"
        className="bg-white border border-stone-200 w-full sm:max-w-2xl max-h-[92vh] sm:max-h-[88vh] flex flex-col shadow-xl rounded-t-2xl sm:rounded-2xl pb-[env(safe-area-inset-bottom)] sm:pb-0"
      >
        <div className="sm:hidden flex justify-center pt-2 pb-1">
          <div className="w-10 h-1 rounded-full bg-stone-300" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200">
          <div>
            <h2
              id="demander-transfert-title"
              className="text-[16px] font-bold text-stone-900"
            >
              Demander à l'épicerie
            </h2>
            <p className="text-[12px] text-stone-500 mt-0.5">
              Sélectionnez un ingrédient et la quantité — le système propose les
              produits sources.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-stone-500 hover:text-stone-900 min-w-[44px] min-h-[44px] flex items-center justify-center -mr-2"
            aria-label="Fermer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4">
          {error && (
            <div className="flex items-start gap-2 px-3 py-2 bg-red-50 border border-red-200 rounded-xl">
              <AlertTriangle className="h-4 w-4 text-red-600 shrink-0 mt-0.5" />
              <span className="text-[13px] text-red-700 flex-1">{error}</span>
              <button
                onClick={() => setError('')}
                aria-label="Fermer l'erreur"
                className="text-red-500 min-h-[44px] min-w-[44px] flex items-center justify-center -mr-2"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          <div className="flex flex-col gap-3">
            {lignes.map((ligne, i) => (
              <LigneBlock
                key={i}
                ligne={ligne}
                ingredients={ingredients}
                ingredientsLoading={ingredientsQ.isLoading}
                canRemove={lignes.length > 1}
                onUpdate={(patch) => updateLigne(i, patch)}
                onRemove={() => removeLigne(i)}
              />
            ))}

            <button
              onClick={addLigne}
              className="w-full flex items-center justify-center gap-2 h-12 border border-dashed border-stone-300 text-stone-600 text-[14px] font-medium rounded-xl hover:border-amber-400 hover:text-amber-700 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Ajouter un ingrédient
            </button>
          </div>

          <div>
            <label className="text-[12px] font-semibold text-stone-600 mb-1.5 block">
              Note pour l'épicerie (optionnel)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ex: livraison demain matin, urgent service midi..."
              rows={2}
              maxLength={2000}
              className="w-full bg-white border border-stone-200 rounded-xl px-3 py-2 text-[14px] focus:outline-none focus:border-amber-400 resize-none"
            />
          </div>

          <div className="text-[12px] text-stone-500 text-center">
            {lignesValides.length > 0
              ? `${lignesValides.length} ingrédient${lignesValides.length > 1 ? 's' : ''} à demander`
              : 'Au moins 1 ingrédient avec quantité requis'}
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-3 px-5 py-4 border-t border-stone-100">
          <button
            onClick={onClose}
            className="flex-1 h-12 text-[14px] text-stone-700 font-medium bg-stone-100 rounded-xl hover:bg-stone-200"
          >
            Annuler
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!canSubmit}
            className="flex-1 h-12 text-[14px] font-semibold text-white bg-amber-600 rounded-xl hover:bg-amber-700 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <Send className="h-4 w-4" />
            {mutation.isPending ? 'Envoi…' : 'Envoyer la demande'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Bloc ligne (picker ingrédient + qté + preview résolveur) ─────────────────

function LigneBlock({
  ligne,
  ingredients,
  ingredientsLoading,
  canRemove,
  onUpdate,
  onRemove,
}: {
  ligne: LigneDemande
  ingredients: IngredientRead[]
  ingredientsLoading: boolean
  canRemove: boolean
  onUpdate: (patch: Partial<LigneDemande>) => void
  onRemove: () => void
}) {
  const [search, setSearch] = useState(ligne.ingredient_nom)
  const [pickerOpen, setPickerOpen] = useState(false)

  useEffect(() => setSearch(ligne.ingredient_nom), [ligne.ingredient_nom])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return ingredients.slice(0, 20)
    return ingredients
      .filter((ing) => ing.nom.toLowerCase().includes(q))
      .slice(0, 20)
  }, [ingredients, search])

  function selectIngredient(ing: IngredientRead) {
    onUpdate({
      ingredient_id: ing.id,
      ingredient_nom: ing.nom,
      unit: ing.unite_stock,
    })
    setSearch(ing.nom)
    setPickerOpen(false)
  }

  function clearSelection() {
    onUpdate({ ingredient_id: null, ingredient_nom: '' })
    setSearch('')
    setPickerOpen(true)
  }

  return (
    <div className="bg-stone-50 border border-stone-200 rounded-xl p-3 flex flex-col gap-2.5">
      {/* Ingrédient picker */}
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0 relative">
          <label className="text-[11px] font-semibold text-stone-600 mb-1 block">
            Ingrédient <span className="text-red-500">*</span>
          </label>
          {ligne.ingredient_id ? (
            <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 h-11">
              <span className="flex-1 text-[14px] text-stone-800 font-medium truncate">
                {ligne.ingredient_nom}
              </span>
              <button
                type="button"
                onClick={clearSelection}
                className="text-stone-400 hover:text-stone-700 p-1"
                aria-label="Changer d'ingrédient"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 bg-white border border-stone-200 rounded-lg px-3 h-11">
              <Search className="h-3.5 w-3.5 text-stone-400 shrink-0" />
              <input
                type="text"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setPickerOpen(true)
                  onUpdate({ ingredient_nom: e.target.value })
                }}
                onFocus={() => setPickerOpen(true)}
                placeholder={ingredientsLoading ? 'Chargement…' : 'Tapez pour chercher'}
                className="flex-1 bg-transparent text-[14px] text-stone-900 focus:outline-none"
              />
            </div>
          )}

          {pickerOpen && !ligne.ingredient_id && (
            <div className="absolute z-10 left-0 right-0 mt-1 bg-white border border-stone-200 rounded-lg shadow-lg max-h-56 overflow-y-auto">
              {filtered.length === 0 && (
                <div className="px-3 py-2 text-[12px] text-stone-400 italic">
                  Aucun ingrédient trouvé
                </div>
              )}
              {filtered.map((ing) => (
                <button
                  key={ing.id}
                  type="button"
                  onClick={() => selectIngredient(ing)}
                  className="w-full text-left px-3 py-2 hover:bg-amber-50 border-b border-stone-50 last:border-b-0"
                >
                  <div className="text-[13px] font-medium text-stone-800">
                    {ing.nom}
                  </div>
                  <div className="text-[10px] text-stone-500">
                    Stock {ing.stock_actuel} {ing.unite_stock}
                    {ing.stock_actuel <= ing.stock_alerte && (
                      <span className="ml-2 text-amber-700 font-semibold">
                        ⚠ sous seuil
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
        {canRemove && (
          <button
            onClick={onRemove}
            aria-label="Supprimer la ligne"
            className="mt-6 text-stone-400 hover:text-red-600 min-h-[44px] min-w-[44px] flex items-center justify-center"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Quantité */}
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label className="text-[11px] font-semibold text-stone-600 mb-1 block">
            Quantité <span className="text-red-500">*</span>
          </label>
          <input
            type="number"
            step="0.001"
            min="0.001"
            value={ligne.quantity}
            onChange={(e) => onUpdate({ quantity: e.target.value })}
            placeholder="0"
            className="w-full h-11 bg-white border border-stone-200 rounded-lg px-3 text-[14px] focus:outline-none focus:border-amber-400"
          />
        </div>
        <div className="h-11 flex items-center px-3 bg-stone-100 rounded-lg text-[13px] text-stone-600 font-medium min-w-[48px] justify-center">
          {ligne.unit}
        </div>
      </div>

      {/* Note */}
      <div>
        <label className="text-[11px] font-semibold text-stone-600 mb-1 block">
          Note (optionnel)
        </label>
        <input
          type="text"
          value={ligne.notes}
          onChange={(e) => onUpdate({ notes: e.target.value })}
          placeholder="Ex: marque préférée, BIO si possible..."
          maxLength={1000}
          className="w-full h-10 bg-white border border-stone-200 rounded-lg px-3 text-[13px] focus:outline-none focus:border-amber-400"
        />
      </div>

      {/* Preview résolveur (si ingrédient choisi + qty valide) */}
      {ligne.ingredient_id && Number(ligne.quantity) > 0 && (
        <ResolvePreviewInline
          ingredientId={ligne.ingredient_id}
          qteBesoin={Number(ligne.quantity)}
        />
      )}
    </div>
  )
}

// ── Preview résolveur temps réel ────────────────────────────────────────────

function ResolvePreviewInline({
  ingredientId,
  qteBesoin,
}: {
  ingredientId: number
  qteBesoin: number
}) {
  const [debounced, setDebounced] = useState(qteBesoin)
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(qteBesoin), 400)
    return () => window.clearTimeout(t)
  }, [qteBesoin])

  const query = useQuery<ResolveResponse>({
    queryKey: ['resolve-preview', ingredientId, debounced],
    queryFn: () =>
      ingredientSourcingApi.resolvePreview(ingredientId, { qte_besoin: debounced }),
    enabled: debounced > 0,
  })

  if (query.isLoading) {
    return (
      <div className="text-[11px] text-stone-400 italic px-1">
        Calcul de la proposition…
      </div>
    )
  }
  if (query.isError) {
    return (
      <div className="text-[11px] text-red-600 bg-red-50 rounded px-2 py-1">
        Erreur preview : {normalizeError(query.error).message}
      </div>
    )
  }
  const data = query.data
  if (!data) return null

  if (data.items.length === 0) {
    return (
      <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
        ⚠ Aucun produit épicerie mappé pour cet ingrédient.{' '}
        <span className="opacity-75">
          Configurez les sources dans la fiche ingrédient.
        </span>
      </div>
    )
  }

  const couverturePct = (parseFloat(data.qte_couverte_totale) / parseFloat(data.qte_besoin)) * 100
  const complete = data.couverture_complete

  return (
    <div
      className={`border rounded-lg px-2.5 py-1.5 ${
        complete
          ? 'bg-emerald-50 border-emerald-200'
          : 'bg-amber-50 border-amber-200'
      }`}
    >
      <div className="text-[11px] font-semibold mb-1 flex items-center gap-1.5">
        {complete ? (
          <>
            <CheckCircle className="h-3 w-3 text-emerald-600" />
            <span className="text-emerald-700">Couverture complète</span>
          </>
        ) : (
          <>
            <AlertTriangle className="h-3 w-3 text-amber-600" />
            <span className="text-amber-700">
              Couverture {couverturePct.toFixed(0)}% — déficit {data.deficit}
            </span>
          </>
        )}
      </div>
      <ul className="text-[11px] text-stone-700 space-y-0.5">
        {data.items.map((it) => (
          <li key={it.produit_id} className="flex justify-between gap-2">
            <span className="truncate">
              #{it.ordre + 1} {it.produit_designation}
            </span>
            <span className="font-mono text-stone-900 shrink-0">
              {parseFloat(it.qte_prelevee_unites_vente).toFixed(2)}{' '}
              {it.produit_unite_vente}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
