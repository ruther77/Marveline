// StockSideSheet — panneau latéral inline (split-view, non-bloquant)
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { X, ExternalLink, Clock } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { normalizeError } from '@shared/errors/normalizer'
import { useToast } from '@shared/components/ui/Toast'
import type { IngredientRead, MouvementStockRead, TypeMouvementStock } from '@/types/restaurant-v2'

// ── Config ────────────────────────────────────────────────────────────────────

type TypeManuel = Extract<TypeMouvementStock, 'entree' | 'consommation' | 'inventaire' | 'perte'>

const TYPES_MOUV: TypeManuel[] = ['entree', 'consommation', 'inventaire', 'perte']

const TYPES_LABELS: Record<TypeManuel, string> = {
  entree: 'Entrée',
  consommation: 'Conso.',
  inventaire: 'Inventaire',
  perte: 'Perte',
}

const TYPES_COLORS: Record<TypeManuel, { idle: string; active: string; dot: string }> = {
  entree:      { idle: 'bg-emerald-50 text-emerald-700 border border-emerald-100',  active: 'bg-emerald-600 text-white border border-emerald-600',  dot: 'bg-emerald-500' },
  consommation:{ idle: 'bg-red-50 text-red-600 border border-red-100',              active: 'bg-red-600 text-white border border-red-600',          dot: 'bg-red-500' },
  inventaire:  { idle: 'bg-blue-50 text-blue-700 border border-blue-100',           active: 'bg-blue-600 text-white border border-blue-600',        dot: 'bg-blue-500' },
  perte:       { idle: 'bg-orange-50 text-orange-700 border border-orange-100',     active: 'bg-orange-500 text-white border border-orange-500',    dot: 'bg-orange-400' },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDatetime(iso: string): string {
  const d = new Date(iso)
  const today = new Date()
  const isToday =
    d.getDate() === today.getDate() &&
    d.getMonth() === today.getMonth() &&
    d.getFullYear() === today.getFullYear()
  if (isToday) {
    return `Aujourd'hui ${d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`
  }
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }) +
    ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

function fmtCout(cts: number): string {
  if (cts === 0) return '—'
  return (cts / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

// ── MouvRow ───────────────────────────────────────────────────────────────────

function MouvRow({ m }: { m: MouvementStockRead }) {
  const isPos = m.quantite >= 0
  const type = m.type_mouvement as TypeManuel
  const colors = TYPES_COLORS[type] ?? TYPES_COLORS.perte
  return (
    <div className="flex items-center gap-2.5 py-2.5 border-b border-stone-100 last:border-0">
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${colors.dot}`} />
      <span className="text-[12px] text-stone-600 flex-1 min-w-0 truncate">
        {TYPES_LABELS[type] ?? type}
        {m.notes ? <span className="text-stone-400"> · {m.notes}</span> : null}
      </span>
      <span className={`text-[12px] font-mono font-semibold shrink-0 ${isPos ? 'text-emerald-600' : 'text-red-500'}`}>
        {isPos ? '+' : ''}{m.quantite} {m.ingredient_unite}
      </span>
      <span className="text-[10px] text-stone-400 shrink-0">{fmtDatetime(m.date_mouvement)}</span>
    </div>
  )
}

// ── StockSideSheet ────────────────────────────────────────────────────────────

export function StockSideSheet({ ing, onClose }: { ing: IngredientRead; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()

  const [typeMouv, setTypeMouv] = useState<TypeManuel>('entree')
  const [quantite, setQuantite] = useState('')
  const [notes, setNotes] = useState('')

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  const { data: histData } = useQuery({
    queryKey: ['restaurant-mouvements', ing.id],
    queryFn: () => restaurantApi.listMouvementsIngredient({ ingredient_id: ing.id, per_page: 8 }),
    staleTime: 15_000,
  })
  const historique = histData?.items ?? []

  const mutation = useMutation({
    mutationFn: () =>
      restaurantApi.ajusterStockIngredient(ing.id, {
        type_mouvement: typeMouv,
        quantite: parseFloat(quantite),
        notes: notes.trim() || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-ingredients'] })
      qc.invalidateQueries({ queryKey: ['restaurant-mouvements', ing.id] })
      toast.success('Stock ajusté', `${ing.nom} — ${TYPES_LABELS[typeMouv]} enregistrée`)
      setQuantite('')
      setNotes('')
    },
    onError: err => {
      toast.error("Erreur", normalizeError(err).message)
    },
  })

  const qty = parseFloat(quantite)
  const canSubmit = quantite.trim() !== '' && !isNaN(qty) && qty > 0 && !mutation.isPending

  const statutColor =
    ing.statut === 'rupture' ? 'text-red-600 bg-red-50' :
    ing.statut === 'bas'     ? 'text-amber-600 bg-amber-50' :
                                'text-emerald-700 bg-emerald-50'

  return (
    <div
      role="complementary"
      aria-label={`Détail ${ing.nom}`}
      className="w-full md:w-[360px] shrink-0 flex flex-col border-l border-stone-200 bg-white overflow-hidden"
    >
      {/* ── En-tête ──────────────────────────────────────────────────── */}
      <div className="px-5 pt-5 pb-4 border-b border-stone-100 shrink-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="text-[16px] font-bold text-stone-900 tracking-tight truncate">{ing.nom}</h2>
            <div className="flex items-center gap-2 mt-1">
              {ing.categorie && (
                <span className="text-[11px] text-stone-400">{ing.categorie}</span>
              )}
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${statutColor}`}>
                {ing.statut === 'rupture' ? 'Rupture' : ing.statut === 'bas' ? 'Stock bas' : 'OK'}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-900 transition-colors shrink-0 mt-0.5" aria-label="Fermer">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Métriques clés */}
        <div className="mt-4 grid grid-cols-2 gap-2">
          <div className="bg-stone-50 rounded-lg px-3 py-2.5">
            <p className="text-[10px] font-semibold text-stone-400 uppercase tracking-wide">Stock actuel</p>
            <p className="text-[18px] font-bold font-mono text-stone-900 leading-tight mt-0.5">
              {ing.stock_actuel}
              <span className="text-[12px] font-medium text-stone-400 ml-1">{ing.unite_stock}</span>
            </p>
          </div>
          <div className="bg-stone-50 rounded-lg px-3 py-2.5">
            <p className="text-[10px] font-semibold text-stone-400 uppercase tracking-wide">Seuil alerte</p>
            <p className="text-[18px] font-bold font-mono text-stone-900 leading-tight mt-0.5">
              {ing.stock_alerte}
              <span className="text-[12px] font-medium text-stone-400 ml-1">{ing.unite_stock}</span>
            </p>
          </div>
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px] text-stone-400">
          <span>
            Coût&nbsp;
            <span className="font-medium text-stone-600">{fmtCout(ing.cout_unitaire_cts)}</span>
          </span>
          <span>
            Dernière entrée&nbsp;
            <span className="font-medium text-stone-600">
              {ing.derniere_entree
                ? new Date(ing.derniere_entree).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
                : '—'}
            </span>
          </span>
          <Link to="/catalogue" className="flex items-center gap-0.5 text-amber-600 hover:underline">
            Config <ExternalLink className="h-2.5 w-2.5" />
          </Link>
        </div>
      </div>

      {/* ── Corps scrollable ─────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">

        {/* Ajustement */}
        <div className="px-5 py-4 border-b border-stone-100">
          <p className="text-[12px] font-semibold text-stone-700 mb-3">Enregistrer un mouvement</p>

          {/* Type */}
          <div className="grid grid-cols-2 gap-1.5 mb-3">
            {TYPES_MOUV.map(t => (
              <button
                key={t}
                type="button"
                onClick={() => setTypeMouv(t)}
                className={[
                  'px-3 py-2 rounded-lg text-[12px] font-semibold transition-all',
                  typeMouv === t ? TYPES_COLORS[t].active : TYPES_COLORS[t].idle + ' hover:opacity-80',
                ].join(' ')}
              >
                {TYPES_LABELS[t]}
              </button>
            ))}
          </div>

          {/* Quantité */}
          <div className="mb-2">
            <label className="text-[11px] text-stone-500 mb-1 block">
              Quantité <span className="text-stone-400">({ing.unite_stock})</span>
            </label>
            <input
              type="number"
              min={0}
              step={0.1}
              value={quantite}
              onChange={e => setQuantite(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[14px] font-mono text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
              placeholder="0.0"
            />
          </div>

          {/* Note */}
          <div className="mb-3">
            <label className="text-[11px] text-stone-500 mb-1 block">Note <span className="text-stone-400">(optionnel)</span></label>
            <input
              type="text"
              value={notes}
              onChange={e => setNotes(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
              placeholder="Ex : livraison fournisseur"
            />
          </div>

          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={!canSubmit}
            className="w-full py-2.5 text-[13px] font-semibold bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-40 transition-colors"
          >
            {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>

        {/* Historique */}
        <div className="px-5 py-4">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="h-3.5 w-3.5 text-stone-400" />
            <p className="text-[12px] font-semibold text-stone-700">Mouvements récents</p>
          </div>
          {historique.length === 0 ? (
            <p className="text-[12px] text-stone-400 text-center py-6">Aucun mouvement enregistré</p>
          ) : (
            historique.map(m => <MouvRow key={m.id} m={m} />)
          )}
        </div>
      </div>
    </div>
  )
}
