// FC_EPICERIE_INVENTAIRE.md §5 — Route : /epicerie/inventaire
// Rôles : staff (lecture), manager (écriture) | Tenant : tenant_id = 2

import { useState, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Search, Package, AlertTriangle, TrendingDown, DollarSign,
  Check, X, RefreshCw, ChevronDown, History, ClipboardList,
  ScanLine, Loader2,
} from 'lucide-react'

import { epicerieApi } from '@/api/epicerie'
import { margeCategoriesApi } from '@/api/categories'
import { useMassaCorpAuthStore } from '@shared/stores/massacorpAuthStore'
import { normalizeError } from '@shared/errors/normalizer'
import { useToast } from '@shared/components/ui/Toast'
import { ViewToggle } from '@shared/components/ui/ViewToggle'
import { Tabs, TabList, TabTrigger, TabContent } from '@shared/components/ui/Tabs'
import { QRScanner } from '@shared/components/ui/QRScanner'
import { cn } from '@shared/lib/utils'
import { ProductDetailModal } from '@/components/ProductDetailModal'
import { Pagination } from '@/components/Pagination'
import type {
  EpicerieStockRead,
  TypeAjustement,
} from '@/types/epicerie-v2'

// ─── Constantes ──────────────────────────────────────────────────────────────

const BADGE_ETAT = {
  ok:      { label: 'OK',      cls: 'bg-[#1d7d4a]/10 text-[#1d7d4a]' },
  bas:     { label: 'Stock bas', cls: 'bg-[#92400e]/10 text-[#92400e]' },
  rupture: { label: 'Rupture',  cls: 'bg-[#991b1b]/10 text-[#991b1b]' },
} as const

const BADGE_MOUVEMENT: Record<string, { label: string; cls: string }> = {
  ENTREE:               { label: 'Entrée',     cls: 'bg-[#1d7d4a]/10 text-[#1d7d4a]' },
  SORTIE:               { label: 'Sortie',     cls: 'bg-[#92400e]/10 text-[#92400e]' },
  AJUSTEMENT:           { label: 'Correction', cls: 'bg-[#4338ca]/10 text-[#4338ca]' },
  PERTE:                { label: 'Perte',      cls: 'bg-[#991b1b]/10 text-[#991b1b]' },
  VENTE:                { label: 'Vente',      cls: 'bg-[#059669]/10 text-[#059669]' },
  TRANSFERT_RESTAURANT: { label: 'Transfert',  cls: 'bg-[#6d28d9]/10 text-[#6d28d9]' },
}

// Types de mouvement exposés dans la modal (FC §4 — VENTE et TRANSFERT_RESTAURANT exclus)
const TYPES_AJUSTEMENT: { key: TypeAjustement; label: string }[] = [
  { key: 'ENTREE',     label: 'Entrée' },
  { key: 'SORTIE',     label: 'Sortie' },
  { key: 'AJUSTEMENT', label: 'Correction' },
  { key: 'PERTE',      label: 'Perte' },
]

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatEur(centimes: number): string {
  return (centimes / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function useDebounce(delay = 300) {
  const [debounced, setDebounced] = useState('')
  const timer = useRef<ReturnType<typeof setTimeout>>()
  const update = useCallback((v: string) => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setDebounced(v), delay)
  }, [delay])
  return { debounced, update }
}

// ─── StatsBar ────────────────────────────────────────────────────────────────
// FC §5 — 4 stat-cards : total_articles, nb_ruptures, nb_stock_bas, valeur_stock_cts

function StatsBar() {
  const { data } = useQuery({
    queryKey: ['epicerie-stock-stats'],
    queryFn: () => epicerieApi.getStockStats(),
    staleTime: 30_000,
  })

  const cards = [
    { label: 'Total articles', value: data?.total_articles ?? '—', icon: <Package className="h-4 w-4" />, accent: 'text-gray-700' },
    { label: 'Ruptures', value: data?.nb_ruptures ?? '—', icon: <AlertTriangle className="h-4 w-4" />, accent: 'text-[#991b1b]' },
    { label: 'Stock bas', value: data?.nb_stock_bas ?? '—', icon: <TrendingDown className="h-4 w-4" />, accent: 'text-[#92400e]' },
    { label: 'Valeur stock', value: data ? formatEur(data.valeur_stock_cts) : '—', icon: <DollarSign className="h-4 w-4" />, accent: 'text-[#059669]' },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
      {cards.map(c => (
        <div key={c.label} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <div className={cn('flex items-center gap-2 text-xs text-gray-400 mb-1', c.accent)}>
            {c.icon}<span>{c.label}</span>
          </div>
          <p className={cn('text-xl font-bold', c.accent)}>{String(c.value)}</p>
        </div>
      ))}
    </div>
  )
}

// ─── CelluleSeuilEditable ─────────────────────────────────────────────────────
// FC §4 — édition inline seuil alerte (clic → input → onBlur/Enter → PUT /seuil)

interface CelluleSeuilProps {
  produitId: number
  seuil: number
  isManager: boolean
}

function CelluleSeuilEditable({ produitId, seuil, isManager }: CelluleSeuilProps) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(String(seuil))
  const qc = useQueryClient()

  const { mutate } = useMutation({
    mutationFn: (newSeuil: number) => epicerieApi.updateSeuil(produitId, { seuil: newSeuil }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['epicerie-stock'] }),
  })

  function confirm() {
    const n = parseFloat(val)
    if (!isNaN(n) && n >= 0 && n !== seuil) mutate(n)
    setEditing(false)
  }

  function cancel() {
    setVal(String(seuil))
    setEditing(false)
  }

  if (!isManager) return <span className="text-gray-400">{seuil}</span>

  if (editing) {
    return (
      <input
        autoFocus
        type="number"
        min="0"
        value={val}
        onChange={e => setVal(e.target.value)}
        onBlur={confirm}
        onKeyDown={e => { if (e.key === 'Enter') confirm(); if (e.key === 'Escape') cancel() }}
        className="w-16 text-right px-1 py-0.5 text-sm border border-[#059669] rounded focus:outline-none"
      />
    )
  }

  return (
    <button
      onClick={() => setEditing(true)}
      title="Cliquer pour modifier le seuil"
      className="text-gray-400 hover:text-gray-700 hover:underline cursor-pointer"
    >
      {seuil}
    </button>
  )
}

// ─── AjustementModal ──────────────────────────────────────────────────────────
// FC §5 — 4 boutons type, quantité float +/−, raison optionnel

interface AjustementModalProps {
  stock: EpicerieStockRead
  onClose: () => void
}

function AjustementModal({ stock, onClose }: AjustementModalProps) {
  const { success: toastOk, error: toastErr } = useToast()
  const qc = useQueryClient()
  const [type, setType] = useState<TypeAjustement>('ENTREE')
  const [quantite, setQuantite] = useState(1)
  const [raison, setRaison] = useState('')

  const { mutate, isPending } = useMutation({
    mutationFn: () => epicerieApi.ajusterStock({ produit_id: stock.produit_id, type_ajustement: type, quantite, raison: raison || null }),
    onSuccess: () => {
      toastOk('Stock mis à jour')
      qc.invalidateQueries({ queryKey: ['epicerie-stock'] })
      qc.invalidateQueries({ queryKey: ['epicerie-stock-stats'] })
      onClose()
    },
    onError: (err: unknown) => toastErr('Erreur', normalizeError(err).message),
  })

  return (
    <div className="fixed inset-0 bg-black/35 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-[420px]">
        <div className="flex justify-between items-center px-5 pt-5 pb-4 border-b border-gray-100">
          <div>
            <h3 className="font-semibold text-gray-800">Ajuster le stock</h3>
            <p className="text-xs text-gray-400 mt-0.5">{stock.designation} — {stock.quantite} en stock</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
        </div>

        <div className="p-5 space-y-4">
          {/* Type mouvement */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">Type de mouvement</p>
            <div className="grid grid-cols-2 gap-1.5">
              {TYPES_AJUSTEMENT.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setType(key)}
                  className={cn(
                    'py-2 text-sm font-medium rounded-lg border transition-all',
                    type === key
                      ? 'border-[#059669] bg-[#059669]/8 text-[#059669] font-semibold'
                      : 'border-gray-200 text-gray-500 hover:border-[#059669]',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Quantité */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">Quantité</p>
            <div className="flex items-center justify-center gap-6">
              <button
                onClick={() => setQuantite(q => Math.max(0.1, parseFloat((q - 1).toFixed(1))))}
                className="w-9 h-9 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-50 flex items-center justify-center text-lg"
              >−</button>
              <span className="text-2xl font-bold text-gray-800 w-16 text-center">{quantite}</span>
              <button
                onClick={() => setQuantite(q => parseFloat((q + 1).toFixed(1)))}
                className="w-9 h-9 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-50 flex items-center justify-center text-lg"
              >+</button>
            </div>
          </div>

          {/* Note optionnelle */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">Note (optionnel)</p>
            <textarea
              value={raison}
              onChange={e => setRaison(e.target.value)}
              placeholder="Ex : livraison METRO, démarque inconnue…"
              rows={2}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg resize-y focus:ring-2 focus:ring-[#059669] focus:outline-none"
            />
          </div>
        </div>

        <div className="flex gap-2 px-5 pb-5">
          <button onClick={onClose} className="flex-1 py-2.5 border border-gray-200 text-gray-600 text-sm font-medium rounded-xl hover:bg-gray-50 transition-colors">
            Annuler
          </button>
          <button
            onClick={() => mutate()}
            disabled={isPending}
            className="flex-1 py-2.5 bg-[#059669] hover:bg-[#047857] disabled:opacity-45 text-white text-sm font-semibold rounded-xl transition-colors"
          >
            {isPending ? 'Enregistrement…' : 'Enregistrer le mouvement'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── LigneStock ──────────────────────────────────────────────────────────────

function formatVolume(ml: number): string {
  if (ml >= 1000 && ml % 1000 === 0) return `${ml / 1000}L`
  if (ml >= 1000) return `${(ml / 1000).toFixed(2).replace(/\.?0+$/, '')}L`
  if (ml >= 100 && ml % 10 === 0) return `${ml / 10}cL`
  return `${ml}mL`
}

function formatContenance(row: EpicerieStockRead): string {
  const vol = row.volume_unitaire_ml ? formatVolume(row.volume_unitaire_ml) : null
  if (row.colisage && row.colisage > 1 && vol) return `${row.colisage} × ${vol}`
  if (row.colisage && row.colisage > 1 && row.unite_base) return `${row.colisage} ${row.unite_base}`
  if (row.colisage && row.colisage > 1) return `lot de ${row.colisage}`
  if (vol) return vol
  if (row.conditionnement) return row.conditionnement
  if (row.unite_base) return row.unite_base
  return '—'
}

interface LigneStockProps {
  row: EpicerieStockRead
  isManager: boolean
  onAjuster: (row: EpicerieStockRead) => void
  onDetail: (row: EpicerieStockRead) => void
}

function LigneStock({ row, isManager, onAjuster, onDetail }: LigneStockProps) {
  const { cls, label } = BADGE_ETAT[row.statut_badge]
  const qtyColor = row.statut_badge === 'rupture' ? 'text-[#991b1b]' : row.statut_badge === 'bas' ? 'text-[#92400e]' : 'text-gray-800'

  function stop(e: React.MouseEvent | React.KeyboardEvent) { e.stopPropagation() }

  return (
    <tr
      onClick={() => onDetail(row)}
      className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors cursor-pointer"
    >
      <td className="py-2.5 px-4 font-medium text-gray-800">{row.designation}</td>
      <td className="py-2.5 px-4 text-gray-400 text-sm">{row.categorie}</td>
      <td className="py-2.5 px-4 text-gray-400 text-sm">{row.fournisseur_source ?? '—'}</td>
      <td className="py-2.5 px-4 text-gray-500 text-sm">{formatContenance(row)}</td>
      <td className="py-2.5 px-4 text-right font-mono text-gray-500 text-sm">{formatEur(row.prix_achat_cts)}</td>
      <td className="py-2.5 px-4 text-right font-mono text-gray-800 text-sm font-semibold">{formatEur(row.prix_unitaire_cts)}</td>
      <td className={cn('py-2.5 px-4 text-right font-bold', qtyColor)}>{row.quantite}</td>
      <td className="py-2.5 px-4 text-right text-gray-400" onClick={stop}>
        <CelluleSeuilEditable produitId={row.produit_id} seuil={row.seuil_alerte} isManager={isManager} />
      </td>
      <td className="py-2.5 px-4">
        <span className={cn('inline-flex px-2 py-0.5 rounded text-xs font-semibold', cls)}>{label}</span>
      </td>
      <td className="py-2.5 px-4 text-xs text-gray-400">{row.derniere_mise_a_jour ? fmtDate(row.derniere_mise_a_jour) : '—'}</td>
      <td className="py-2.5 px-4" onClick={stop}>
        {isManager && (
          <button
            onClick={(e) => { e.stopPropagation(); onAjuster(row) }}
            className="text-xs px-2.5 py-1 border border-gray-200 rounded-lg text-gray-600 hover:border-[#059669] hover:text-[#059669] transition-colors"
          >
            Ajuster
          </button>
        )}
      </td>
    </tr>
  )
}

// ─── CarteStock ───────────────────────────────────────────────────────────────

function CarteStock({ row, onDetail }: LigneStockProps) {
  const { cls } = BADGE_ETAT[row.statut_badge]
  const qtyColor = row.statut_badge === 'rupture' ? 'text-[#991b1b]' : row.statut_badge === 'bas' ? 'text-[#92400e]' : 'text-gray-800'

  return (
    <button
      onClick={() => onDetail(row)}
      className="w-full text-left bg-white border border-gray-100 rounded-xl p-4 hover:border-[#059669] hover:shadow-sm transition-all"
    >
      <p className="text-[13.5px] font-semibold text-gray-800 mb-1 line-clamp-2">{row.designation}</p>
      <p className="text-xs text-gray-400 mb-3">{row.categorie}</p>
      <p className={cn('text-[22px] font-bold tracking-tight', qtyColor)}>{row.quantite}</p>
      <p className="text-[11.5px] text-gray-400 mt-1">
        Mini : {row.seuil_alerte}
        <span className={cn('ml-2 px-1.5 py-0.5 rounded text-[11px] font-semibold', cls)}>
          {BADGE_ETAT[row.statut_badge].label}
        </span>
      </p>
    </button>
  )
}

// ─── OngletVueStock ───────────────────────────────────────────────────────────
// FC §5 — TableauStock + GrilleCartes + filtres + AjustementModal

function OngletVueStock({ isManager }: { isManager: boolean }) {
  const { error: toastErr } = useToast()
  const { debounced: search, update: setSearch } = useDebounce()
  const [categorie, setCategorie] = useState('')
  const [fournisseur, setFournisseur] = useState('')
  const [isLow, setIsLow] = useState(false)
  const [isEmpty, setIsEmpty] = useState(false)
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table')
  const [page, setPage] = useState(1)
  const [selectedRow, setSelectedRow] = useState<EpicerieStockRead | null>(null)
  const [selectedDetail, setSelectedDetail] = useState<EpicerieStockRead | null>(null)
  const [scanMode, setScanMode] = useState(false)
  const [scanKey, setScanKey] = useState(0)
  const [scanLoading, setScanLoading] = useState(false)

  async function handleScannedEan(ean: string) {
    if (scanLoading) return
    setScanLoading(true)
    try {
      const produit = await epicerieApi.getProduitByEan(ean.trim())
      const stock = await epicerieApi.getStockByProduit(produit.id)
      setSelectedDetail(stock)
    } catch (err: unknown) {
      const msg = normalizeError(err).message || 'Produit inconnu'
      toastErr(`EAN ${ean}`, msg)
    } finally {
      setScanLoading(false)
      setScanKey(k => k + 1) // remount le scanner pour prochain scan
    }
  }

  function closeDetail() {
    setSelectedDetail(null)
    if (scanMode) setScanKey(k => k + 1) // relance scanner après fermeture modal
  }

  function exitScanMode() {
    setScanMode(false)
    setSelectedDetail(null)
  }

  const { data: allCategories = [] } = useQuery({
    queryKey: ['epicerie-marge-categories'],
    queryFn: () => margeCategoriesApi.getAll(),
    staleTime: 60_000,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['epicerie-stock', search, categorie, fournisseur, isLow, isEmpty, page],
    queryFn: () => epicerieApi.listStock({
      search, categorie, fournisseur,
      is_low: isLow || undefined, is_empty: isEmpty || undefined,
      page, per_page: 20,
    }),
    staleTime: 15_000,
  })

  const rows = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / 20)

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div className="flex flex-wrap gap-2 items-center bg-white rounded-xl border border-gray-100 shadow-sm p-3">
        <div className="relative flex-1 min-w-44">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
          <input
            placeholder="Rechercher un article..."
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#059669] focus:outline-none"
          />
        </div>
        <select
          value={categorie}
          onChange={e => { setCategorie(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#059669] focus:outline-none text-gray-600"
        >
          <option value="">Toutes catégories</option>
          {allCategories.map(c => (
            <option key={c.categorie} value={c.categorie}>{c.categorie}</option>
          ))}
        </select>
        <select
          value={fournisseur}
          onChange={e => { setFournisseur(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#059669] focus:outline-none text-gray-600"
        >
          <option value="">Tous fournisseurs</option>
          {[...new Set(rows.map(r => r.fournisseur_source).filter(Boolean))].map(f => <option key={f!} value={f!}>{f}</option>)}
        </select>
        <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer">
          <input type="checkbox" checked={isLow} onChange={e => { setIsLow(e.target.checked); setPage(1) }} className="accent-[#059669]" />
          Stock bas
        </label>
        <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer">
          <input type="checkbox" checked={isEmpty} onChange={e => { setIsEmpty(e.target.checked); setPage(1) }} className="accent-[#059669]" />
          Ruptures
        </label>
        <button
          onClick={() => setScanMode(true)}
          className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[#059669] text-white rounded-lg hover:bg-[#047857] transition-colors"
        >
          <ScanLine className="h-3.5 w-3.5" /> Mode scan
        </button>
        <ViewToggle mode={viewMode} onChange={setViewMode} />
      </div>

      {/* Contenu */}
      {isLoading ? (
        <div className="space-y-3 animate-pulse py-4">{[1,2,3,4].map(i=><div key={i} className="h-16 bg-gray-100 rounded-xl" />)}</div>
      ) : viewMode === 'table' ? (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                {['Article', 'Catégorie', 'Fournisseur', 'Contenance', 'Achat HT', 'Vente TTC', 'Stock', 'Mini', 'État', 'MAJ', ''].map(h => (
                  <th key={h} className="py-2.5 px-4 text-left text-xs font-medium text-gray-400">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(r => <LigneStock key={r.id} row={r} isManager={isManager} onAjuster={setSelectedRow} onDetail={setSelectedDetail} />)}
              {rows.length === 0 && (
                <tr><td colSpan={10} className="py-12 text-center text-sm text-gray-400">Aucun article trouvé</td></tr>
              )}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 text-sm text-gray-500">
              <span>{total} articles</span>
              <div className="flex gap-2">
                <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="px-3 py-1 border rounded-lg disabled:opacity-40">←</button>
                <span className="px-3 py-1">{page} / {totalPages}</span>
                <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)} className="px-3 py-1 border rounded-lg disabled:opacity-40">→</button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-3">
          {rows.map(r => <CarteStock key={r.id} row={r} isManager={isManager} onAjuster={setSelectedRow} onDetail={setSelectedDetail} />)}
          {rows.length === 0 && <p className="col-span-full text-center py-12 text-sm text-gray-400">Aucun article trouvé</p>}
        </div>
      )}

      {selectedRow && <AjustementModal stock={selectedRow} onClose={() => setSelectedRow(null)} />}
      {selectedDetail && <ProductDetailModal stock={selectedDetail} onClose={closeDetail} />}

      {scanMode && (
        <ScanOverlay
          key={scanKey}
          loading={scanLoading}
          onScan={handleScannedEan}
          onError={(err) => toastErr('Erreur caméra', err.message)}
          onExit={exitScanMode}
          hidden={!!selectedDetail}
        />
      )}
    </div>
  )
}

// ─── ScanOverlay : scanner persistant pour mode scan continu ─────────────────

interface ScanOverlayProps {
  loading: boolean
  onScan: (ean: string) => void
  onError: (err: Error) => void
  onExit: () => void
  hidden: boolean
}

function ScanOverlay({ loading, onScan, onError, onExit, hidden }: ScanOverlayProps) {
  return (
    <div
      className={cn(
        'fixed inset-0 z-40 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4',
        hidden && 'opacity-0 pointer-events-none',
      )}
    >
      <div className="w-full max-w-md bg-white rounded-2xl overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-700">
            <ScanLine className="h-4 w-4 text-[#059669]" /> Scanner inventaire
          </h3>
          <button
            onClick={onExit}
            className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-800"
          >
            <X className="h-3.5 w-3.5" /> Quitter
          </button>
        </div>
        <div className="bg-black aspect-video">
          <QRScanner
            active={!loading}
            mode="scan"
            onScan={onScan}
            onError={onError}
          />
        </div>
        <div className="px-4 py-3 text-xs text-gray-500 bg-gray-50/50 flex items-center justify-center gap-1.5 min-h-[40px]">
          {loading ? (
            <><Loader2 className="h-3 w-3 animate-spin" /> Recherche…</>
          ) : (
            <>Pointez un code-barres pour ouvrir la fiche produit</>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── OngletComptage ───────────────────────────────────────────────────────────
// FC §4 — GET /stock?per_page=1000, saisie comptée, écart coloré, POST /comptage

interface ComptageRow {
  produit_id: number
  designation: string
  categorie: string
  stock_systeme: number
  quantite_comptee: number | null
  notes_ligne: string
}

function OngletComptage({ isManager }: { isManager: boolean }) {
  const { success: toastOk, error: toastErr } = useToast()
  const [notesGlobal, setNotesGlobal] = useState('')
  const [rows, setRows] = useState<ComptageRow[]>([])
  const [submitted, setSubmitted] = useState(false)
  const [initialized, setInitialized] = useState(false)

  const { data: stockData, isLoading } = useQuery({
    queryKey: ['epicerie-stock-comptage-init'],
    queryFn: async () => {
      const PAGE_SIZE = 100
      const first = await epicerieApi.listStock({ per_page: PAGE_SIZE, page: 1 })
      const totalPages = Math.ceil(first.total / PAGE_SIZE)
      if (totalPages <= 1) return first
      const rest = await Promise.all(
        Array.from({ length: totalPages - 1 }, (_, i) =>
          epicerieApi.listStock({ per_page: PAGE_SIZE, page: i + 2 })
        )
      )
      return { ...first, items: [...first.items, ...rest.flatMap(r => r.items)] }
    },
    enabled: !submitted,
    staleTime: Infinity,
  })

  // Initialiser les rows une seule fois quand les données arrivent
  if (stockData && !initialized) {
    setRows(stockData.items.map(s => ({
      produit_id: s.produit_id,
      designation: s.designation,
      categorie: s.categorie ?? '',
      stock_systeme: s.quantite,
      quantite_comptee: null,
      notes_ligne: '',
    })))
    setInitialized(true)
  }

  const nbComptes = rows.filter(r => r.quantite_comptee !== null).length
  const pct = rows.length > 0 ? (nbComptes / rows.length) * 100 : 0
  const hasEcart = rows.some(r => r.quantite_comptee !== null && r.quantite_comptee !== r.stock_systeme)
  const canValider = isManager && notesGlobal.trim().length > 0 && hasEcart

  const { mutate: valider, isPending } = useMutation({
    mutationFn: () => epicerieApi.validerComptage({
      lignes: rows
        .filter(r => r.quantite_comptee !== null)
        .map(r => ({ produit_id: r.produit_id, quantite_comptee: r.quantite_comptee!, notes: r.notes_ligne || null })),
      notes: notesGlobal,
    }),
    onSuccess: res => {
      toastOk('Inventaire validé', `${res.nb_ajustements} ajustements sur ${res.nb_lignes} articles`)
      setSubmitted(true)
    },
    onError: (err: unknown) => toastErr('Erreur', normalizeError(err).message),
  })

  function updateRow(idx: number, patch: Partial<ComptageRow>) {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, ...patch } : r))
  }

  function reinitialiser() {
    setRows(prev => prev.map(r => ({ ...r, quantite_comptee: null, notes_ligne: '' })))
    setNotesGlobal('')
    setSubmitted(false)
    setInitialized(false)
  }

  if (isLoading) return <div className="space-y-3 animate-pulse py-4">{[1,2,3,4].map(i=><div key={i} className="h-16 bg-gray-100 rounded-xl" />)}</div>

  return (
    <div className="flex flex-col gap-4">
      {/* Barre progression */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-gray-400">{nbComptes} / {rows.length} articles comptés</span>
          <span className="text-xs font-medium text-[#059669]">{Math.round(pct)}%</span>
        </div>
        <div className="h-1.5 bg-gray-200 rounded-full"><div className="h-full bg-[#059669] rounded-full transition-all" style={{ width: `${pct}%` }} /></div>
      </div>

      {/* Notes globales (obligatoires — FC §4) */}
      <input
        type="text"
        value={notesGlobal}
        onChange={e => setNotesGlobal(e.target.value)}
        placeholder="Identifiant de session — obligatoire (ex : Inventaire mensuel mars 2026)"
        className="px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-[#059669] focus:outline-none"
      />

      {/* Tableau comptage */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/50">
              {['Article', 'Catégorie', 'Stock système', 'Quantité comptée', 'Différence', 'Notes ligne'].map(h => (
                <th key={h} className="py-2.5 px-4 text-left text-xs font-medium text-gray-400">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const ecart = r.quantite_comptee !== null ? r.quantite_comptee - r.stock_systeme : null
              const ecartColor = ecart === null ? 'text-gray-300' : ecart > 0 ? 'text-[#1d7d4a] font-semibold' : ecart < 0 ? 'text-[#991b1b] font-semibold' : 'text-gray-400'
              return (
                <tr key={r.produit_id} className="border-b border-gray-50 hover:bg-gray-50/50">
                  <td className="py-2 px-4 font-medium text-gray-800 text-sm">{r.designation}</td>
                  <td className="py-2 px-4 text-xs text-gray-400">{r.categorie}</td>
                  <td className="py-2 px-4 text-right text-gray-400 text-sm">{r.stock_systeme}</td>
                  <td className="py-2 px-4 text-right">
                    <input
                      type="number"
                      min="0"
                      step="0.1"
                      placeholder="—"
                      value={r.quantite_comptee ?? ''}
                      onChange={e => updateRow(i, { quantite_comptee: e.target.value === '' ? null : parseFloat(e.target.value) })}
                      disabled={!isManager}
                      className="w-20 text-right px-2 py-1 text-sm border border-gray-200 rounded-lg focus:border-[#059669] focus:outline-none disabled:opacity-40"
                    />
                  </td>
                  <td className={cn('py-2 px-4 text-right text-sm', ecartColor)}>
                    {ecart === null ? '—' : ecart > 0 ? `+${ecart}` : String(ecart)}
                  </td>
                  <td className="py-2 px-4">
                    <input
                      type="text"
                      placeholder="—"
                      value={r.notes_ligne}
                      onChange={e => updateRow(i, { notes_ligne: e.target.value })}
                      disabled={!isManager}
                      className="w-full px-2 py-1 text-xs border border-gray-100 rounded-lg focus:border-[#059669] focus:outline-none disabled:opacity-40"
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Actions */}
      <div className="flex gap-2 justify-end">
        <button onClick={reinitialiser} className="flex items-center gap-2 px-4 py-2.5 border border-gray-200 text-gray-600 text-sm font-medium rounded-xl hover:bg-gray-50 transition-colors">
          <RefreshCw className="h-4 w-4" />Réinitialiser
        </button>
        <button
          onClick={() => valider()}
          disabled={!canValider || isPending}
          className="flex items-center gap-2 px-4 py-2.5 bg-[#059669] hover:bg-[#047857] disabled:opacity-45 text-white text-sm font-semibold rounded-xl transition-colors"
        >
          <Check className="h-4 w-4" />
          {isPending ? 'Validation…' : 'Valider l\'inventaire'}
        </button>
      </div>
    </div>
  )
}

// ─── OngletHistorique ─────────────────────────────────────────────────────────
// FC §5 — filtres type + produit_id + dates, tableau mouvements signé

const MOUVEMENTS_PER_PAGE = 25

function OngletHistorique() {
  const [filterType, setFilterType] = useState('')
  const [filterProduitId, setFilterProduitId] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['epicerie-mouvements', filterType, filterProduitId, dateDebut, dateFin, page],
    queryFn: () => epicerieApi.listMouvements({
      type: filterType || undefined,
      produit_id: filterProduitId ? parseInt(filterProduitId) : undefined,
      date_debut: dateDebut || undefined,
      date_fin: dateFin || undefined,
      page,
      per_page: MOUVEMENTS_PER_PAGE,
    }),
    staleTime: 15_000,
    placeholderData: prev => prev,
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <div className="flex flex-col gap-3">
      {/* Filtres */}
      <div className="flex flex-wrap gap-2 bg-white rounded-xl border border-gray-100 shadow-sm p-3">
        <select
          value={filterType}
          onChange={e => { setFilterType(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#059669] focus:outline-none text-gray-600"
        >
          <option value="">Tous les types</option>
          {Object.entries(BADGE_MOUVEMENT).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <input
          type="number"
          placeholder="ID article…"
          value={filterProduitId}
          onChange={e => { setFilterProduitId(e.target.value); setPage(1) }}
          className="w-32 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#059669] focus:outline-none"
        />
        <input type="date" value={dateDebut} onChange={e => { setDateDebut(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#059669] focus:outline-none text-gray-600"
        />
        <input type="date" value={dateFin} onChange={e => { setDateFin(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#059669] focus:outline-none text-gray-600"
        />
      </div>

      {/* Tableau mouvements */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="space-y-3 animate-pulse py-4">{[1,2,3,4].map(i=><div key={i} className="h-16 bg-gray-100 rounded-xl" />)}</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                {['Type', 'Article', 'Quantité', 'Utilisateur', 'Date & heure', 'Note'].map(h => (
                  <th key={h} className="py-2.5 px-4 text-left text-xs font-medium text-gray-400">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(m => {
                const badge = BADGE_MOUVEMENT[m.type] ?? { label: m.type, cls: 'bg-gray-100 text-gray-600' }
                const signedPositive = m.signed_quantite > 0
                return (
                  <tr key={m.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                    <td className="py-2.5 px-4">
                      <span className={cn('inline-flex px-2 py-0.5 rounded text-xs font-semibold', badge.cls)}>{badge.label}</span>
                    </td>
                    <td className="py-2.5 px-4 text-sm font-medium text-gray-800">{m.produit_designation}</td>
                    <td className={cn('py-2.5 px-4 text-right text-sm font-semibold', signedPositive ? 'text-[#1d7d4a]' : 'text-[#991b1b]')}>
                      {signedPositive ? `+${m.signed_quantite}` : String(m.signed_quantite)}
                    </td>
                    <td className="py-2.5 px-4 text-sm text-gray-400">{m.created_by_name ?? '—'}</td>
                    <td className="py-2.5 px-4 text-xs text-gray-400">{fmtDate(m.date_mouvement)}</td>
                    <td className="py-2.5 px-4 text-xs text-gray-400">{m.notes ?? '—'}</td>
                  </tr>
                )
              })}
              {items.length === 0 && (
                <tr><td colSpan={6} className="py-12 text-center text-sm text-gray-400">Aucun mouvement trouvé</td></tr>
              )}
            </tbody>
          </table>
        )}
        {total > MOUVEMENTS_PER_PAGE && (
          <div className="px-4 py-3 border-t border-gray-100">
            <Pagination
              page={page}
              total={total}
              perPage={MOUVEMENTS_PER_PAGE}
              onPageChange={setPage}
              itemLabel="mouvement"
            />
          </div>
        )}
      </div>
    </div>
  )
}

// ─── InventairePage ───────────────────────────────────────────────────────────

export default function InventairePage() {
  const { user } = useMassaCorpAuthStore()
  const isManager = user?.role === 'manager'

  return (
    <div className="p-4 bg-gray-50 min-h-full">
      <div className="mb-4">
        <h1 className="text-xl font-bold text-gray-800">Inventaire</h1>
      </div>

      <StatsBar />

      <Tabs defaultValue="stock">
        <TabList variant="underline" className="mb-4 bg-white rounded-t-xl border border-b-0 border-gray-100 px-4">
          <TabTrigger value="stock" icon={<Package className="h-4 w-4" />} variant="underline">Stock</TabTrigger>
          <TabTrigger value="comptage" icon={<ClipboardList className="h-4 w-4" />} variant="underline">Comptage physique</TabTrigger>
          <TabTrigger value="historique" icon={<History className="h-4 w-4" />} variant="underline">Historique mouvements</TabTrigger>
        </TabList>

        <TabContent value="stock"><OngletVueStock isManager={isManager} /></TabContent>
        <TabContent value="comptage"><OngletComptage isManager={isManager} /></TabContent>
        <TabContent value="historique"><OngletHistorique /></TabContent>
      </Tabs>
    </div>
  )
}
