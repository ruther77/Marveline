// Route : /_massacorp/restaurant/cuisine
// Vue cuisine — marmites du jour + lancer marmite (3 etapes) + tickets en cours

import { useState, useCallback, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, Check, AlertTriangle, Plus, Minus, RefreshCw } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { normalizeError } from '@shared/errors/normalizer'
import { classifyTicket, LANE_TITLES, type KdsLane } from '@/lib/kdsLanes'
import type {
  TypePreparationRead,
  StockRequisRead,
  TicketCuisineLigne,
  TicketCuisineTicket,
  InstancePreparationRead,
  StatutBadge,
  StockBadge,
} from '@/types/restaurant-v2'

const STATUT_BADGE_CLS: Record<StatutBadge, string> = {
  dispo:  'bg-emerald-50 text-emerald-700 border border-emerald-200',
  faible: 'bg-amber-50 text-amber-700 border border-amber-200',
  epuise: 'bg-red-50 text-red-600 border border-red-100',
}

const STATUT_BADGE_LABEL: Record<StatutBadge, string> = {
  dispo:  'Dispo',
  faible: 'Faible',
  epuise: 'Epuise',
}

const STOCK_BADGE_CLS: Record<StockBadge, string> = {
  full: 'bg-emerald-50 text-emerald-700',
  low:  'bg-amber-50 text-amber-700',
  out:  'bg-red-50 text-red-600',
}

const BAR_COLOR_BY_BADGE: Record<StatutBadge, string> = {
  dispo:  'bg-emerald-500',
  faible: 'bg-amber-500',
  epuise: 'bg-red-500',
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtHeure(iso: string | null | undefined): string {
  if (!iso) return '--:--'
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function statutTicketBadge(s: string): { label: string; cls: string } {
  if (s === 'ENVOYEE') return { label: 'Envoye',   cls: 'bg-stone-100 text-stone-500 border border-stone-200' }
  if (s === 'LANCEE')  return { label: 'En cours', cls: 'bg-blue-50 text-blue-600 border border-blue-100' }
  return                      { label: 'Pret',     cls: 'bg-emerald-50 text-emerald-700 border border-emerald-200' }
}

// ─── useTicketAge ─────────────────────────────────────────────────────────────

type TicketUrgency = 'normal' | 'warning' | 'urgent'

function useTicketAge(heureEnvoi: string | null | undefined): { label: string; urgency: TicketUrgency } {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(id)
  }, [])

  if (!heureEnvoi) return { label: '', urgency: 'normal' }

  const minutes = Math.floor((now - new Date(heureEnvoi).getTime()) / 60_000)
  if (minutes < 1)  return { label: "à l'instant", urgency: 'normal' }
  if (minutes < 10) return { label: `${minutes} min`, urgency: 'normal' }
  if (minutes < 20) return { label: `${minutes} min`, urgency: 'warning' }
  return { label: `${minutes} min`, urgency: 'urgent' }
}

const URGENCY_BORDER: Record<TicketUrgency, string> = {
  normal:  'border-l-[3px] border-l-transparent',
  warning: 'border-l-[3px] border-l-amber-400',
  urgent:  'border-l-[3px] border-l-red-500',
}

const URGENCY_AGE_CLS: Record<TicketUrgency, string> = {
  normal:  'text-stone-400',
  warning: 'text-amber-600',
  urgent:  'text-red-500 font-semibold',
}

// ─── Skeletons (C1) ───────────────────────────────────────────────────────────

function SkeletonMarmite() {
  return (
    <div className="animate-pulse flex flex-col gap-2">
      {[0, 1].map(i => (
        <div key={i} className="bg-stone-200 rounded-xl px-3 py-2.5">
          <div className="h-3 bg-stone-300 rounded w-2/3 mb-2" />
          <div className="h-[5px] bg-stone-300 rounded-full w-full mb-2" />
          <div className="h-2 bg-stone-300 rounded w-1/3" />
        </div>
      ))}
    </div>
  )
}

function SkeletonTickets() {
  return (
    <div className="animate-pulse flex flex-col gap-3">
      {[0, 1].map(i => (
        <div key={i} className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 bg-stone-50 border-b border-stone-200">
            <div className="h-3 bg-stone-200 rounded w-1/3" />
          </div>
          <div className="px-4 py-3 flex flex-col gap-2">
            <div className="h-3 bg-stone-200 rounded w-3/4" />
            <div className="h-3 bg-stone-200 rounded w-1/2" />
          </div>
        </div>
      ))}
    </div>
  )
}

function SkeletonRecettes() {
  return (
    <div className="animate-pulse flex flex-col gap-2">
      {[0, 1, 2].map(i => <div key={i} className="h-12 bg-stone-200 rounded-xl" />)}
    </div>
  )
}

// ─── AjusterPortionsWidget (C10) ──────────────────────────────────────────────

function AjusterPortionsWidget({ instanceId, onClose }: { instanceId: number; onClose: () => void }) {
  const qc = useQueryClient()
  const [delta, setDelta] = useState(0)
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: () => restaurantApi.ajusterPortions(instanceId, delta),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-marmites'] })
      onClose()
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur ajustement'),
  })

  const deltaLabel = delta > 0 ? `+${delta}` : String(delta)
  const deltaColor = delta < 0 ? 'text-red-600' : delta > 0 ? 'text-emerald-600' : 'text-stone-500'

  return (
    <div className="mt-2 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setDelta(d => d - 1)}
          className="w-8 h-8 rounded-lg border border-stone-200 flex items-center justify-center text-stone-400 hover:bg-stone-50"
          aria-label="Diminuer"
        >
          <Minus className="h-3 w-3" />
        </button>
        <span className={`flex-1 text-center text-[13px] font-bold ${deltaColor}`}>{deltaLabel}</span>
        <button
          onClick={() => setDelta(d => d + 1)}
          className="w-8 h-8 rounded-lg border border-stone-200 flex items-center justify-center text-stone-400 hover:bg-stone-50"
          aria-label="Augmenter"
        >
          <Plus className="h-3 w-3" />
        </button>
      </div>
      {error && <p className="text-[11px] text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={() => mutation.mutate()}
          disabled={delta === 0 || mutation.isPending}
          className="flex-1 bg-amber-600 text-white text-[11.5px] font-semibold rounded-lg py-1.5 hover:bg-amber-700 disabled:opacity-40"
        >
          {mutation.isPending ? '...' : 'Valider'}
        </button>
        <button onClick={onClose} className="text-[11.5px] text-stone-400 hover:text-stone-900 px-2">
          Annuler
        </button>
      </div>
    </div>
  )
}

// ─── MarmiteMiniCard (C4-C10) ─────────────────────────────────────────────────

function MarmiteMiniCard({ m }: { m: InstancePreparationRead }) {
  const [showAjust, setShowAjust] = useState(false)

  return (
    <div className="bg-white border border-stone-200 rounded-xl px-3 py-2.5">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-[13px] font-semibold text-stone-900 truncate">{m.type_preparation_nom}</span>
          {m.est_fraiche && (
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 shrink-0">
              Fraiche
            </span>
          )}
        </div>
        <span className={`text-[10.5px] font-semibold px-2 py-0.5 rounded-full shrink-0 ml-2 ${STATUT_BADGE_CLS[m.statut_badge]}`}>
          {STATUT_BADGE_LABEL[m.statut_badge]}
        </span>
      </div>

      <div className="flex items-center gap-2 mb-1.5">
        <div className="flex-1 h-[5px] bg-stone-200 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${BAR_COLOR_BY_BADGE[m.statut_badge]}`}
            style={{ width: `${m.pourcentage_restant}%` }}
          />
        </div>
        <span className="text-[12px] font-bold text-stone-900 shrink-0">
          {m.portions_restantes}/{m.portions_initiales}
        </span>
      </div>

      <div className="flex items-center gap-2 text-[11px] text-stone-400">
        <span>{fmtHeure(m.heure_lancement)}</span>
        {m.created_by_nom && <span>· {m.created_by_nom}</span>}
      </div>

      {m.proteines_disponibles.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5">
          {m.proteines_disponibles.map(p => (
            <span
              key={p.ingredient_id}
              className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${STOCK_BADGE_CLS[p.stock_badge]}`}
            >
              {p.nom}
            </span>
          ))}
        </div>
      )}

      {!showAjust ? (
        <button
          onClick={() => setShowAjust(true)}
          className="mt-2 w-full text-[11.5px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-lg py-2 hover:bg-amber-100 transition-colors"
        >
          Ajuster portions
        </button>
      ) : (
        <AjusterPortionsWidget instanceId={m.instance_id} onClose={() => setShowAjust(false)} />
      )}
    </div>
  )
}

// ─── FormulaireCreerBase ──────────────────────────────────────────────────────

function FormulaireCreerBase({ onCreated }: { onCreated: () => void }) {
  const qc = useQueryClient()
  const [nom, setNom] = useState('')
  const [portions, setPortions] = useState(10)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: () => restaurantApi.createTypePreparation({
      nom: nom.trim(),
      portions_par_batch: portions,
      notes: notes.trim() || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-types-prep'] })
      setNom('')
      setPortions(10)
      setNotes('')
      setError('')
      onCreated()
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur creation'),
  })

  const canSubmit = nom.trim().length > 0 && portions >= 1

  return (
    <div className="border border-amber-200 bg-amber-50/40 rounded-xl p-3 flex flex-col gap-2.5">
      <span className="text-[12px] font-bold text-amber-700">Nouvelle base / recette</span>
      <div>
        <label className="text-[11.5px] font-semibold text-stone-600 mb-1 block">Nom</label>
        <input
          type="text"
          value={nom}
          onChange={e => setNom(e.target.value)}
          placeholder="Ex : Mafe, Thieboudienne..."
          className="w-full bg-white border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
        />
      </div>
      <div>
        <label className="text-[11.5px] font-semibold text-stone-600 mb-1 block">Portions par batch</label>
        <input
          type="number"
          min={1}
          value={portions}
          onChange={e => setPortions(Number(e.target.value))}
          className="w-full bg-white border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 transition-colors"
        />
      </div>
      <div>
        <label className="text-[11.5px] font-semibold text-stone-600 mb-1 block">Notes (optionnel)</label>
        <input
          type="text"
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Instructions, allergenes..."
          className="w-full bg-white border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 transition-colors"
        />
      </div>
      {error && <p className="text-[11px] text-red-600">{error}</p>}
      <button
        onClick={() => mutation.mutate()}
        disabled={!canSubmit || mutation.isPending}
        className="w-full bg-amber-600 text-white text-[12.5px] font-semibold rounded-lg py-2 hover:bg-amber-700 disabled:opacity-40"
      >
        {mutation.isPending ? 'Creation...' : 'Creer la base'}
      </button>
    </div>
  )
}

// ─── Etape 1 — Choisir la recette ─────────────────────────────────────────────

function Etape1({
  selectedId, onSelect,
}: {
  selectedId: number | null
  onSelect: (id: number, t: TypePreparationRead) => void
}) {
  const [showCreateForm, setShowCreateForm] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['restaurant-types-prep'],
    queryFn: restaurantApi.listTypesPreparation,
    staleTime: 300_000,
  })

  const handleCreated = useCallback(() => setShowCreateForm(false), [])

  if (isLoading) return <SkeletonRecettes />

  const items = data ?? []

  return (
    <div className="flex flex-col gap-2">
      {items.length === 0 && !showCreateForm && (
        <p className="text-[13px] text-stone-400 py-3 text-center">
          Aucune base disponible. Creez-en une pour commencer.
        </p>
      )}

      {items.map((t: TypePreparationRead) => {
        const sel = selectedId === t.id
        return (
          <button
            key={t.id}
            onClick={() => onSelect(t.id, t)}
            className={`text-left px-3 py-2.5 rounded-xl border transition-colors ${
              sel
                ? 'border-amber-400 bg-amber-50'
                : 'border-stone-200 bg-white hover:bg-stone-50'
            }`}
          >
            <div className="text-[13px] font-semibold text-stone-900">{t.nom}</div>
            <div className="text-[11.5px] text-stone-500 mt-0.5">
              {t.portions_par_batch} portions · {t.temps_cuisson_min} min
            </div>
          </button>
        )
      })}

      {showCreateForm ? (
        <FormulaireCreerBase onCreated={handleCreated} />
      ) : (
        <button
          onClick={() => setShowCreateForm(true)}
          className="w-full text-[12.5px] font-semibold text-amber-600 border border-dashed border-amber-300 rounded-xl py-2 hover:bg-amber-50 transition-colors"
        >
          + Creer une nouvelle base
        </button>
      )}
    </div>
  )
}

// ─── Etape 2 — Verifier le stock ──────────────────────────────────────────────

function Etape2({
  typeId, portions, onPortionsChange,
}: {
  typeId: number
  portions: number
  onPortionsChange: (v: number) => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['restaurant-stock-requis', typeId],
    queryFn: () => restaurantApi.getStockRequis(typeId),
    staleTime: 10_000,
  })

  if (isLoading) {
    return (
      <div className="animate-pulse flex flex-col gap-2">
        {[0, 1].map(i => <div key={i} className="h-10 bg-stone-200 rounded-xl" />)}
      </div>
    )
  }

  const stock = data as StockRequisRead | undefined

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        {(stock?.ingredients_requis ?? []).map(ing => (
          <div key={ing.ingredient_id} className="flex items-center gap-2 px-3 py-2 bg-stone-50 border border-stone-200 rounded-lg">
            <span className="text-[12.5px] text-stone-900 flex-1">{ing.nom}</span>
            <span className="text-[11.5px] text-stone-500 font-mono">{ing.quantite_par_batch} {ing.unite}</span>
            <span className={`text-[11px] px-2 py-0.5 rounded-full font-semibold ${
              ing.suffisant
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-red-50 text-red-600'
            }`}>
              {ing.suffisant ? 'OK' : 'Manque'}
            </span>
          </div>
        ))}
      </div>
      <div>
        <label className="text-[12px] font-semibold text-stone-600 mb-1 block">Portions a cuisiner</label>
        <input
          type="number"
          min={1}
          value={portions}
          onChange={e => onPortionsChange(Number(e.target.value))}
          className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
        />
      </div>
    </div>
  )
}

// ─── Etape 3 — Confirmer ──────────────────────────────────────────────────────

function Etape3({
  typeNom, portions, dateCuisine, notes, loading,
  onDateChange, onNotesChange, onLancer,
}: {
  typeNom: string; portions: number; dateCuisine: string; notes: string; loading: boolean
  onDateChange: (v: string) => void; onNotesChange: (v: string) => void; onLancer: () => void
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="bg-stone-50 border border-stone-200 rounded-xl px-3 py-2.5">
        <div className="text-[12px] text-stone-500">Recette</div>
        <div className="text-[13.5px] font-semibold text-stone-900">{typeNom} — {portions} portions</div>
      </div>
      <div>
        <label className="text-[12px] font-semibold text-stone-600 mb-1 block">Date de cuisine</label>
        <input
          type="date"
          value={dateCuisine}
          onChange={e => onDateChange(e.target.value)}
          className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
        />
      </div>
      <div>
        <label className="text-[12px] font-semibold text-stone-600 mb-1 block">Notes (optionnel)</label>
        <input
          type="text"
          value={notes}
          onChange={e => onNotesChange(e.target.value)}
          placeholder="Ex : sans piment..."
          className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-[13px] text-stone-900 focus:outline-none focus:border-amber-400 focus:bg-white transition-colors"
        />
      </div>
      <button
        onClick={onLancer}
        disabled={loading || portions < 1}
        className="w-full bg-amber-600 text-white text-[13px] font-semibold rounded-lg py-2.5 hover:bg-amber-700 disabled:opacity-50"
      >
        {loading ? 'Lancement...' : 'Lancer la marmite'}
      </button>
    </div>
  )
}

// ─── PanelLancerMarmite ───────────────────────────────────────────────────────

function PanelLancerMarmite({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [etape, setEtape] = useState<1 | 2 | 3>(1)
  const [selectedTypeId, setSelectedTypeId] = useState<number | null>(null)
  const [selectedTypeNom, setSelectedTypeNom] = useState('')
  const [portions, setPortions] = useState(1)
  const [dateCuisine, setDateCuisine] = useState(todayIso())
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const lancerMutation = useMutation({
    mutationFn: () => restaurantApi.lancerMarmite({
      type_preparation_id: selectedTypeId!,
      portions_initiales: portions,
      date_cuisine: dateCuisine,
      notes: notes || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-marmites'] })
      setSuccess('Marmite lancee !')
      setEtape(1)
      setSelectedTypeId(null)
      setSelectedTypeNom('')
      setPortions(1)
      setNotes('')
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur lors du lancement'),
  })

  function handleSelectType(id: number, t: TypePreparationRead) {
    setSelectedTypeId(id)
    setSelectedTypeNom(t.nom)
    setPortions(t.portions_par_batch)
  }

  const STEPS = ['Recette', 'Stock', 'Confirmer'] as const
  const stepIdx = etape - 1

  return (
    <div className="border border-amber-200 bg-amber-50/40 rounded-xl p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-bold text-amber-700">Nouvelle marmite</span>
        <button onClick={onClose} className="text-stone-400 hover:text-stone-900 text-lg leading-none">x</button>
      </div>

      <div className="flex items-center gap-1">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center gap-1">
            <div className={`flex items-center gap-1.5 text-[11.5px] font-semibold px-2 py-0.5 rounded-full ${
              i < stepIdx
                ? 'bg-emerald-50 text-emerald-700'
                : i === stepIdx
                ? 'bg-amber-50 text-amber-700'
                : 'text-stone-400'
            }`}>
              {i < stepIdx ? <Check className="h-3 w-3" /> : <span>{i + 1}</span>}
              {label}
            </div>
            {i < STEPS.length - 1 && <ChevronRight className="h-3 w-3 text-stone-300" />}
          </div>
        ))}
      </div>

      {error && (
        <div className="flex items-center gap-2 text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />{error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 text-[12px] text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2">
          <Check className="h-3.5 w-3.5 shrink-0" />{success}
        </div>
      )}

      {etape === 1 && (
        <>
          <Etape1 selectedId={selectedTypeId} onSelect={handleSelectType} />
          <button
            onClick={() => { setError(''); setSuccess(''); setEtape(2) }}
            disabled={!selectedTypeId}
            className="w-full flex items-center justify-center gap-1.5 bg-amber-600 text-white text-[13px] font-semibold rounded-lg py-2.5 hover:bg-amber-700 disabled:opacity-40"
          >
            Suivant <ChevronRight className="h-4 w-4" />
          </button>
        </>
      )}

      {etape === 2 && (
        <>
          <Etape2 typeId={selectedTypeId!} portions={portions} onPortionsChange={setPortions} />
          <button
            onClick={() => { setError(''); setEtape(3) }}
            className="w-full flex items-center justify-center gap-1.5 bg-amber-600 text-white text-[13px] font-semibold rounded-lg py-2.5 hover:bg-amber-700"
          >
            Confirmer <ChevronRight className="h-4 w-4" />
          </button>
        </>
      )}

      {etape === 3 && (
        <Etape3
          typeNom={selectedTypeNom}
          portions={portions}
          dateCuisine={dateCuisine}
          notes={notes}
          loading={lancerMutation.isPending}
          onDateChange={setDateCuisine}
          onNotesChange={setNotes}
          onLancer={() => {
            if (portions < 1) { setError('Minimum 1 portion'); return }
            setError(''); setSuccess(''); lancerMutation.mutate()
          }}
        />
      )}
    </div>
  )
}

// ─── ColonneGauche ────────────────────────────────────────────────────────────

function ColonneGauche() {
  const [showPanel, setShowPanel] = useState(false)

  const { data: marmitesData, isLoading } = useQuery({
    queryKey: ['restaurant-marmites'],
    queryFn: () => restaurantApi.listInstances(),
    staleTime: 15_000,
  })
  const marmites = marmitesData?.items ?? []

  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="flex items-center justify-between mb-3">
          <span className="text-[14px] font-bold text-stone-900">Marmites du jour</span>
          <span className="text-[11px] bg-amber-50 text-amber-700 rounded-full px-2.5 py-0.5 font-semibold">
            {marmites.length} active{marmites.length > 1 ? 's' : ''}
          </span>
        </div>
        {isLoading ? (
          <SkeletonMarmite />
        ) : marmites.length === 0 ? (
          <p className="text-[13px] text-stone-400 py-4 text-center">Aucune marmite active aujourd'hui</p>
        ) : (
          <div className="flex flex-col gap-2">
            {marmites.map(m => <MarmiteMiniCard key={m.instance_id} m={m} />)}
          </div>
        )}
      </div>

      {!showPanel ? (
        <button
          onClick={() => setShowPanel(true)}
          className="w-full bg-amber-600 text-white text-[14px] font-semibold rounded-xl h-12 hover:bg-amber-700"
        >
          + Lancer une nouvelle marmite
        </button>
      ) : (
        <PanelLancerMarmite onClose={() => setShowPanel(false)} />
      )}
    </div>
  )
}

// ─── LigneTicketRow (C11, C14, C15) ──────────────────────────────────────────

function LigneTicketRow({ ligne }: { ligne: TicketCuisineLigne }) {
  const qc = useQueryClient()
  const badge = statutTicketBadge(ligne.statut_plat)

  const updateMutation = useMutation({
    mutationFn: (statut: string) => restaurantApi.updateStatutPlat(ligne.ligne_id, statut),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['restaurant-tickets-cuisine'] }),
  })

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[13px] font-semibold text-stone-900 truncate">
            {ligne.variante_nom}
            {ligne.side_nom && <span className="text-stone-500 font-normal"> + {ligne.side_nom}</span>}
          </span>
          {!ligne.stock_disponible && (
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-red-50 text-red-600 shrink-0">
              Stock epuise
            </span>
          )}
        </div>
        {ligne.notes && (
          <div className="text-[11px] text-amber-600 italic mt-0.5 truncate">{ligne.notes}</div>
        )}
      </div>

      <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${badge.cls}`}>
        {badge.label}
      </span>

      {ligne.statut_plat === 'ENVOYEE' && (
        <button
          onClick={() => updateMutation.mutate('LANCEE')}
          disabled={updateMutation.isPending}
          className="text-[12px] font-semibold px-3 h-11 min-w-[44px] bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 shrink-0"
        >
          Lancer
        </button>
      )}
      {ligne.statut_plat === 'LANCEE' && (
        <button
          onClick={() => updateMutation.mutate('PRETE')}
          disabled={updateMutation.isPending}
          className="text-[12px] font-semibold px-3 h-11 min-w-[44px] bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 shrink-0"
        >
          Prêt
        </button>
      )}
    </div>
  )
}

// ─── TicketGroupCard (C12, C13, C16) ─────────────────────────────────────────

function TicketGroupCard({ ticket }: { ticket: TicketCuisineTicket }) {
  const qc = useQueryClient()
  const age = useTicketAge(ticket.heure_envoi)

  const marquerPretMutation = useMutation({
    mutationFn: () => restaurantApi.marquerPret(ticket.commande_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['restaurant-tickets-cuisine'] }),
  })

  const nbActives = ticket.lignes.filter(l => l.statut_plat !== 'PRETE').length

  return (
    <div className={`bg-white border border-stone-200 rounded-xl overflow-hidden ${URGENCY_BORDER[age.urgency]}`}>
      <div className="flex items-center gap-2 px-4 py-2.5 bg-stone-50 border-b border-stone-200">
        <span className="text-[12px] font-bold text-stone-900">
          {ticket.table_numero ? `Table ${ticket.table_numero}` : `Commande #${ticket.commande_id}`}
        </span>
        {ticket.heure_envoi && (
          <span className="text-[11px] text-stone-400">{fmtHeure(ticket.heure_envoi)}</span>
        )}
        {age.label && (
          <span className={`text-[11px] ${URGENCY_AGE_CLS[age.urgency]}`}>{age.label}</span>
        )}
        <span className="ml-auto text-[11px] font-semibold bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full">
          {ticket.lignes.length} plat{ticket.lignes.length > 1 ? 's' : ''}
        </span>
      </div>

      <div className="divide-y divide-stone-100">
        {ticket.lignes.map(l => <LigneTicketRow key={l.ligne_id} ligne={l} />)}
      </div>

      {nbActives > 0 && (
        <div className="px-3 py-2.5 border-t border-stone-200 bg-stone-50">
          <button
            onClick={() => marquerPretMutation.mutate()}
            disabled={marquerPretMutation.isPending}
            className="w-full text-[13px] font-semibold h-11 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {marquerPretMutation.isPending ? '...' : `Tout marquer prêt (${nbActives})`}
          </button>
        </div>
      )}
    </div>
  )
}

// ─── KdsKanban (C12) — 3 colonnes Reçues / Préparation / Prêtes ──────────────

const LANE_DOT: Record<KdsLane, string> = {
  recues: 'bg-stone-400',
  preparation: 'bg-amber-500',
  pretes: 'bg-emerald-500',
}

const LANE_HEADER_BG: Record<KdsLane, string> = {
  recues: 'bg-stone-100',
  preparation: 'bg-amber-50',
  pretes: 'bg-emerald-50',
}

function useUrgencyAlert(tickets: TicketCuisineTicket[]) {
  const alertedRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    const now = Date.now()
    for (const t of tickets) {
      if (!t.heure_envoi) continue
      const minutes = Math.floor((now - new Date(t.heure_envoi).getTime()) / 60_000)
      const key = `${t.ticket_id}`
      if (minutes >= 20 && !alertedRef.current.has(key)) {
        alertedRef.current.add(key)
        window.dispatchEvent(new CustomEvent('cuisine:ticket-urgent', {
          detail: { ticket_id: t.ticket_id, table_numero: t.table_numero, minutes },
        }))
      }
    }
  }, [tickets])
}

function KdsLaneColumn({
  lane, tickets, isLoading,
}: { lane: KdsLane; tickets: TicketCuisineTicket[]; isLoading: boolean }) {
  return (
    <div className="flex flex-col min-w-0 bg-white rounded-2xl border border-stone-200 overflow-hidden">
      <div className={`flex items-center gap-2 px-4 h-12 border-b border-stone-200 ${LANE_HEADER_BG[lane]}`}>
        <div className={`h-2.5 w-2.5 rounded-full ${LANE_DOT[lane]}`} />
        <span className="text-[14px] font-bold text-stone-900">{LANE_TITLES[lane]}</span>
        <span className="ml-auto text-[12px] font-semibold text-stone-600 bg-white/80 px-2 py-0.5 rounded-full">
          {tickets.length}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3 min-h-0">
        {isLoading ? (
          <SkeletonTickets />
        ) : tickets.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-2 py-8 text-center">
            {lane === 'pretes' ? (
              <>
                <div className="w-10 h-10 rounded-full bg-emerald-50 flex items-center justify-center">
                  <Check className="h-4 w-4 text-emerald-500" />
                </div>
                <p className="text-[12px] text-stone-400">Aucun plat prêt</p>
              </>
            ) : (
              <p className="text-[12px] text-stone-400">— vide —</p>
            )}
          </div>
        ) : (
          tickets.map(t => <TicketGroupCard key={t.ticket_id} ticket={t} />)
        )}
      </div>
    </div>
  )
}

function KdsKanban() {
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['restaurant-tickets-cuisine'],
    queryFn: restaurantApi.getTicketsCuisine,
    staleTime: 10_000,
    refetchInterval: 15_000,
  })

  const tickets = data?.items ?? []
  useUrgencyAlert(tickets)

  const grouped: Record<KdsLane, TicketCuisineTicket[]> = {
    recues: [], preparation: [], pretes: [],
  }
  for (const t of tickets) grouped[classifyTicket(t)].push(t)

  return (
    <div className="flex flex-col h-full w-full overflow-hidden">
      <div className="flex items-center justify-between mb-3 px-1">
        <span className="text-[14px] font-bold text-stone-900">Kitchen Display System</span>
        <span className="flex items-center gap-1.5 text-[11px] text-stone-400">
          <RefreshCw className={`h-3 w-3 ${isFetching ? 'animate-spin' : ''}`} />
          Maj 15 s
        </span>
      </div>
      <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-3 min-h-0 overflow-y-auto md:overflow-hidden">
        {(['recues', 'preparation', 'pretes'] as const).map(lane => (
          <KdsLaneColumn key={lane} lane={lane} tickets={grouped[lane]} isLoading={isLoading} />
        ))}
      </div>
    </div>
  )
}

// ─── CuisinePage ──────────────────────────────────────────────────────────────

export default function CuisinePage() {
  const [view, setView] = useState<'kds' | 'marmites'>('kds')

  return (
    <div className="flex flex-col min-h-0 h-full bg-stone-50">
      {/* Header */}
      <div className="px-4 sm:px-6 py-3 border-b border-stone-200 bg-white flex items-center gap-3">
        <h1 className="text-[16px] font-semibold text-stone-900 shrink-0">Cuisine</h1>
        {/* Toggle vue mobile/tablette portrait */}
        <div className="flex lg:hidden items-center gap-1 bg-stone-100 rounded-xl p-1 ml-auto">
          <button
            onClick={() => setView('kds')}
            className={`text-[13px] font-semibold px-4 h-10 rounded-lg transition-colors ${
              view === 'kds' ? 'bg-white text-stone-900 shadow-sm' : 'text-stone-600'
            }`}
          >
            Tickets
          </button>
          <button
            onClick={() => setView('marmites')}
            className={`text-[13px] font-semibold px-4 h-10 rounded-lg transition-colors ${
              view === 'marmites' ? 'bg-white text-stone-900 shadow-sm' : 'text-stone-600'
            }`}
          >
            Marmites
          </button>
        </div>
      </div>

      {/* Body — desktop : 2 colonnes. Mobile/tablette portrait : 1 vue selon toggle. */}
      <div className="flex-1 overflow-hidden flex">
        <div
          className={`${
            view === 'marmites' ? 'flex' : 'hidden'
          } lg:flex w-full lg:w-[300px] lg:shrink-0 lg:border-r border-stone-200 px-4 sm:px-6 py-5 overflow-y-auto bg-white`}
        >
          <div className="w-full">
            <ColonneGauche />
          </div>
        </div>
        <div
          className={`${
            view === 'kds' ? 'flex' : 'hidden'
          } lg:flex flex-1 min-w-0 px-3 sm:px-4 py-5 overflow-hidden`}
        >
          <KdsKanban />
        </div>
      </div>
    </div>
  )
}
