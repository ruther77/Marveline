// Route : /_app/marges
// Gestion des taux de marge par catégorie — grille de cards

import { useState, useMemo, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { massacorpApi } from '@/api'
import { normalizeError } from '@shared/errors/normalizer'

interface MargeRead {
  categorie: string
  taux_marge_centieme: number
  taux_pct: number
}

interface MargesResponse {
  marges: MargeRead[]
  total: number
}

const GROUP_META: Record<string, { label: string; emoji: string; color: string }> = {
  ALC:   { label: 'Alcools',          emoji: '🍷', color: 'from-purple-500/10 to-purple-500/5 border-purple-200' },
  BOIS:  { label: 'Boissons',         emoji: '🥤', color: 'from-blue-500/10 to-blue-500/5 border-blue-200' },
  BOUL:  { label: 'Boulangerie',      emoji: '🥐', color: 'from-amber-500/10 to-amber-500/5 border-amber-200' },
  COND:  { label: 'Condiments',       emoji: '🧂', color: 'from-yellow-500/10 to-yellow-500/5 border-yellow-200' },
  CONS:  { label: 'Conserves',        emoji: '🥫', color: 'from-orange-500/10 to-orange-500/5 border-orange-200' },
  ENTR:  { label: 'Entretien',        emoji: '🧹', color: 'from-cyan-500/10 to-cyan-500/5 border-cyan-200' },
  EPIC:  { label: 'Épicerie sèche',   emoji: '🍚', color: 'from-stone-500/10 to-stone-500/5 border-stone-200' },
  FL:    { label: 'Fruits & Légumes', emoji: '🥬', color: 'from-green-500/10 to-green-500/5 border-green-200' },
  FRAIS: { label: 'Frais',            emoji: '🥩', color: 'from-red-500/10 to-red-500/5 border-red-200' },
  HYG:   { label: 'Hygiène',          emoji: '🧴', color: 'from-pink-500/10 to-pink-500/5 border-pink-200' },
  LAIT:  { label: 'Produits laitiers',emoji: '🧀', color: 'from-yellow-500/10 to-yellow-500/5 border-yellow-200' },
  MONDE: { label: 'Monde',            emoji: '🌍', color: 'from-teal-500/10 to-teal-500/5 border-teal-200' },
  PRO:   { label: 'Professionnel',    emoji: '📦', color: 'from-slate-500/10 to-slate-500/5 border-slate-300' },
  SNACK: { label: 'Snacking',         emoji: '🍿', color: 'from-rose-500/10 to-rose-500/5 border-rose-200' },
  SUCR:  { label: 'Sucré',            emoji: '🍫', color: 'from-pink-500/10 to-pink-500/5 border-pink-200' },
  SURG:  { label: 'Surgelés',         emoji: '🧊', color: 'from-sky-500/10 to-sky-500/5 border-sky-200' },
  AUTRE: { label: 'Autre',            emoji: '📋', color: 'from-gray-500/10 to-gray-500/5 border-gray-200' },
}

function getPrefix(cat: string): string {
  return cat.split('_')[0]
}

function formatEur(centimes: number): string {
  return (centimes / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

// ── Sub-categories popover ───────────────────────────────────────────────────

function SubCatPopover({ items, edits, onEdit, onClose }: {
  items: MargeRead[]
  edits: Map<string, number>
  onEdit: (cat: string, val: number) => void
  onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  return (
    <div ref={ref} className="absolute z-50 top-full left-0 right-0 mt-2 bg-white rounded-xl border border-slate-200 shadow-xl p-3 space-y-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-slate-500">Ajuster par sous-catégorie</span>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xs">fermer</button>
      </div>
      {items.map(m => {
        const val = edits.get(m.categorie) ?? m.taux_marge_centieme
        const label = m.categorie.split('_').slice(1).join(' ') || m.categorie
        return (
          <div key={m.categorie} className="flex items-center gap-2">
            <span className="text-[11px] text-slate-600 w-40 truncate capitalize font-medium">{label.toLowerCase()}</span>
            <input
              type="range" min={0} max={10000} step={100} value={val}
              onChange={e => onEdit(m.categorie, Number(e.target.value))}
              className="w-24 h-1 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-emerald-500 shrink-0"
            />
            <span className="text-xs font-mono text-slate-700 w-10 text-right">{(val / 100).toFixed(0)}%</span>
          </div>
        )
      })}
    </div>
  )
}

// ── Group Card ───────────────────────────────────────────────────────────────

function GroupCard({ prefix, items, edits, onSetGroup, onEdit }: {
  prefix: string
  items: MargeRead[]
  edits: Map<string, number>
  onSetGroup: (prefix: string, val: number) => void
  onEdit: (cat: string, val: number) => void
}) {
  const [showSub, setShowSub] = useState(false)
  const meta = GROUP_META[prefix] || { label: prefix, emoji: '📋', color: 'from-gray-500/10 to-gray-500/5 border-gray-200' }

  const avg = useMemo(() => {
    if (items.length === 0) return 3000
    const sum = items.reduce((s, m) => s + (edits.get(m.categorie) ?? m.taux_marge_centieme), 0)
    return Math.round(sum / items.length)
  }, [items, edits])

  const pct = avg / 100
  const exVente = Math.round(1000 * (1 + avg / 10000) * 1.2)
  const hasEdits = items.some(m => edits.has(m.categorie))

  return (
    <div className={`relative rounded-2xl border bg-gradient-to-br p-4 ${meta.color} transition-shadow hover:shadow-md`}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-2xl">{meta.emoji}</span>
        <span className="text-sm font-semibold text-slate-800">{meta.label}</span>
        {hasEdits && <span className="w-2 h-2 rounded-full bg-emerald-500 ml-auto" />}
      </div>

      {/* Big percentage */}
      <div className="text-3xl font-bold text-slate-800 mb-1">
        {pct.toFixed(0)}<span className="text-lg text-slate-400">%</span>
      </div>

      {/* Price example */}
      <div className="text-xs text-slate-500 mb-3">
        10€ HT → <span className="font-medium text-slate-700">{formatEur(exVente)}</span> TTC
      </div>

      {/* Slider */}
      <input
        type="range" min={0} max={10000} step={100} value={avg}
        onChange={e => onSetGroup(prefix, Number(e.target.value))}
        className="w-full h-2 bg-white/60 rounded-lg appearance-none cursor-pointer accent-emerald-500"
      />

      {/* Détail link */}
      {items.length > 1 && (
        <button
          onClick={() => setShowSub(!showSub)}
          className="mt-2 text-[11px] text-slate-400 hover:text-slate-600 transition-colors"
        >
          {showSub ? 'Masquer' : `${items.length} sous-catégories`}
        </button>
      )}

      {/* Sub-categories popover */}
      {showSub && (
        <SubCatPopover
          items={items}
          edits={edits}
          onEdit={onEdit}
          onClose={() => setShowSub(false)}
        />
      )}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function MargesPage() {
  const qc = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [edits, setEdits] = useState<Map<string, number>>(new Map())

  const { data, isLoading } = useQuery<MargesResponse>({
    queryKey: ['epicerie-marges'],
    queryFn: () => massacorpApi.get('/epicerie/marges'),
  })

  const saveMut = useMutation({
    mutationFn: (marges: { categorie: string; taux_marge_centieme: number }[]) =>
      massacorpApi.put('/epicerie/marges', { marges }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['epicerie-marges'] })
      setEdits(new Map())
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const recalcMut = useMutation({
    mutationFn: () => massacorpApi.post('/epicerie/marges/recalculate-prices') as Promise<{ updated: number }>,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['epicerie-catalogue-pos'] })
      qc.invalidateQueries({ queryKey: ['epicerie-stock-list'] })
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur'),
  })

  const grouped = useMemo(() => {
    const map = new Map<string, MargeRead[]>()
    for (const m of (data?.marges ?? [])) {
      const prefix = getPrefix(m.categorie)
      if (!map.has(prefix)) map.set(prefix, [])
      map.get(prefix)!.push(m)
    }
    return map
  }, [data])

  const handleSetGroup = (prefix: string, value: number) => {
    const items = grouped.get(prefix) ?? []
    setEdits(prev => {
      const next = new Map(prev)
      for (const m of items) next.set(m.categorie, value)
      return next
    })
  }

  const handleEdit = (cat: string, val: number) => {
    setEdits(prev => {
      const next = new Map(prev)
      next.set(cat, val)
      return next
    })
  }

  const handleApply = () => {
    if (edits.size === 0) return
    const marges = Array.from(edits.entries()).map(([categorie, taux_marge_centieme]) => ({
      categorie, taux_marge_centieme,
    }))
    saveMut.mutate(marges, {
      onSuccess: () => setTimeout(() => recalcMut.mutate(), 300),
    })
  }

  const dirty = edits.size > 0

  if (isLoading) {
    return (
      <div className="w-full px-6 py-6">
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-44 bg-slate-100 rounded-2xl animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="w-full px-6 py-6 space-y-5">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">Marges</h1>
          <p className="text-sm text-slate-400 mt-0.5">Prix vente = Achat HT × (1 + Marge) × (1 + TVA)</p>
        </div>
        <Link
          to="/categories"
          className="text-xs text-slate-400 hover:text-emerald-600 transition-colors"
        >
          Gérer les catégories →
        </Link>
        {dirty && (
          <span className="text-xs text-amber-600 font-medium px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-lg">
            {edits.size} modification{edits.size > 1 ? 's' : ''}
          </span>
        )}
        <button
          onClick={handleApply}
          disabled={!dirty || saveMut.isPending}
          className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-xl transition-colors disabled:opacity-50 shadow-sm"
        >
          {saveMut.isPending ? 'Application…' : 'Appliquer les marges'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-red-600 text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">fermer</button>
        </div>
      )}

      {/* Grid de cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-4">
        {Array.from(grouped.entries()).map(([prefix, items]) => (
          <GroupCard
            key={prefix}
            prefix={prefix}
            items={items}
            edits={edits}
            onSetGroup={handleSetGroup}
            onEdit={handleEdit}
          />
        ))}
      </div>
    </div>
  )
}
