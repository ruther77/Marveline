// Modal détail produit épicerie — lecture infos + historique prix + ajout EAN par scan.
// Triggered : clic ligne InventairePage OU scan EAN en mode scan continu.

import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Package, History, Barcode, Camera, X, Loader2, ScanLine,
} from 'lucide-react'

import { useToast } from '@shared/components/ui/Toast'
import { QRScanner } from '@shared/components/ui/QRScanner'
import { normalizeError } from '@shared/errors/normalizer'
import { cn } from '@shared/lib/utils'

import { epicerieApi } from '@/api/epicerie'
import type {
  EpicerieStockRead,
  PrixHistoriqueItem,
} from '@/types/epicerie-v2'

interface ProductDetailModalProps {
  stock: EpicerieStockRead
  onClose: () => void
}

function formatEur(centimes: number | null | undefined): string {
  if (centimes == null || isNaN(centimes)) return '—'
  return (centimes / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  })
}

const SOURCE_LABEL: Record<string, string> = {
  etl: 'Import facture',
  manual: 'Saisie manuelle',
  recalcul: 'Recalcul',
}

export function ProductDetailModal({ stock, onClose }: ProductDetailModalProps) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 bg-black/35 flex items-start sm:items-center justify-center z-50 p-4 overflow-y-auto"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl my-4 max-h-[calc(100vh-2rem)] flex flex-col">
        <div className="flex justify-between items-start px-5 pt-5 pb-4 border-b border-gray-100 shrink-0">
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-800 truncate" title={stock.designation}>{stock.designation}</h3>
            <p className="text-xs text-gray-400 mt-0.5">{stock.categorie ?? '—'}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 ml-3 shrink-0" aria-label="Fermer">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-5 py-5 space-y-5 overflow-y-auto">
          <ProductHeader stock={stock} />
          <ProductInfos stock={stock} />
          <EansSection produitId={stock.produit_id} />
          <PrixHistorySection produitId={stock.produit_id} />
        </div>
      </div>
    </div>
  )
}

// ─── Header : image + métriques clés ─────────────────────────────────────────

function ProductHeader({ stock }: { stock: EpicerieStockRead }) {
  const qtyColor =
    stock.statut_badge === 'rupture' ? 'text-[#991b1b]'
    : stock.statut_badge === 'bas' ? 'text-[#92400e]'
    : 'text-[#1d7d4a]'

  return (
    <div className="flex gap-4 items-start pb-4 border-b border-gray-100">
      <div className="w-20 h-20 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center overflow-hidden flex-shrink-0">
        {stock.image_url ? (
          <img src={stock.image_url} alt="" className="w-full h-full object-cover" />
        ) : (
          <Package className="h-8 w-8 text-gray-300" />
        )}
      </div>
      <div className="grid grid-cols-3 gap-3 flex-1">
        <Metric label="Stock actuel" value={stock.quantite} valueClass={qtyColor} />
        <Metric label="Prix achat HT" value={formatEur(stock.prix_achat_cts)} />
        <Metric label="Prix vente TTC" value={formatEur(stock.prix_unitaire_cts)} />
      </div>
    </div>
  )
}

function Metric({ label, value, valueClass }: { label: string; value: React.ReactNode; valueClass?: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-gray-400 mb-1">{label}</p>
      <p className={cn('text-lg font-bold text-gray-800 tabular-nums', valueClass)}>{value}</p>
    </div>
  )
}

// ─── Section infos produit ───────────────────────────────────────────────────

function ProductInfos({ stock }: { stock: EpicerieStockRead }) {
  const items: { label: string; value: React.ReactNode }[] = [
    { label: 'Catégorie', value: stock.categorie ?? '—' },
    { label: 'Fournisseur', value: stock.fournisseur_source ?? '—' },
    { label: 'Seuil alerte', value: stock.seuil_alerte },
    { label: 'Dernière MAJ', value: formatDate(stock.derniere_mise_a_jour) },
  ]
  return (
    <div>
      <SectionTitle icon={<Package className="h-4 w-4" />}>Informations</SectionTitle>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        {items.map(it => (
          <div key={it.label} className="flex justify-between border-b border-gray-50 pb-1.5">
            <dt className="text-gray-400">{it.label}</dt>
            <dd className="text-gray-700 font-medium text-right">{it.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

// ─── Section EANs : principal + secondaires + ajout par scan ─────────────────

function EansSection({ produitId }: { produitId: number }) {
  const { success: toastOk, error: toastErr } = useToast()
  const qc = useQueryClient()
  const [scannerOpen, setScannerOpen] = useState(false)
  const [manualEan, setManualEan] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['epicerie-produit-eans', produitId],
    queryFn: () => epicerieApi.getProduitEans(produitId),
  })

  const { mutate: addEan, isPending: isAdding } = useMutation({
    mutationFn: (ean: string) => epicerieApi.addProduitEan(produitId, ean),
    onSuccess: (_res, ean) => {
      toastOk(`EAN ${ean} ajouté`)
      qc.invalidateQueries({ queryKey: ['epicerie-produit-eans', produitId] })
      setScannerOpen(false)
      setManualEan('')
    },
    onError: (err: unknown) => {
      toastErr('Ajout EAN impossible', normalizeError(err).message)
      setScannerOpen(false)
    },
  })

  function handleScanned(ean: string) {
    addEan(ean.trim())
  }

  function handleManualSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (manualEan.trim().length >= 8) addEan(manualEan.trim())
  }

  const principal = data?.ean_principal ?? null
  const secondaires = data?.eans_secondaires ?? []

  return (
    <div>
      <SectionTitle icon={<Barcode className="h-4 w-4" />}>Codes-barres</SectionTitle>

      {isLoading ? (
        <div className="flex gap-2 mb-3">
          <div className="h-7 w-32 bg-gray-100 rounded-md animate-pulse" />
          <div className="h-7 w-32 bg-gray-100 rounded-md animate-pulse" />
        </div>
      ) : (
        <div className="flex flex-wrap gap-2 mb-3">
          {principal && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#059669]/10 text-[#1d7d4a] text-xs font-mono font-semibold">
              {principal}
              <span className="text-[10px] uppercase tracking-wide font-sans">principal</span>
            </span>
          )}
          {secondaires.map(e => (
            <span
              key={e.id}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-gray-100 text-gray-700 text-xs font-mono"
              title={e.source_fournisseur ? `Source : ${e.source_fournisseur}` : undefined}
            >
              {e.ean}
              {e.source_fournisseur && (
                <span className="text-[10px] uppercase tracking-wide font-sans text-gray-400">{e.source_fournisseur}</span>
              )}
            </span>
          ))}
          {!principal && secondaires.length === 0 && (
            <span className="text-xs text-gray-400 italic">Aucun code-barres associé</span>
          )}
        </div>
      )}

      {/* Ajout EAN */}
      {scannerOpen ? (
        <div className="border border-gray-200 rounded-xl p-3 bg-gray-50/50">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-gray-600 flex items-center gap-1.5">
              <ScanLine className="h-3.5 w-3.5" /> Pointez un code-barres vers la caméra
            </p>
            <button
              onClick={() => setScannerOpen(false)}
              className="text-gray-400 hover:text-gray-700"
              aria-label="Fermer le scanner"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="rounded-lg overflow-hidden bg-black">
            <QRScanner
              active={!isAdding}
              mode="scan"
              onScan={handleScanned}
              onError={(err) => toastErr('Erreur caméra', err.message)}
            />
          </div>
          {isAdding && (
            <p className="text-xs text-gray-500 mt-2 flex items-center gap-1.5">
              <Loader2 className="h-3 w-3 animate-spin" /> Ajout en cours…
            </p>
          )}
        </div>
      ) : (
        <div className="flex flex-col sm:flex-row gap-2">
          <button
            onClick={() => setScannerOpen(true)}
            disabled={isAdding}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-sm bg-[#059669] text-white rounded-lg hover:bg-[#047857] transition-colors disabled:opacity-50"
          >
            <Camera className="h-4 w-4" /> Scanner un code-barres
          </button>
          <form onSubmit={handleManualSubmit} className="flex-1 flex gap-2">
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              placeholder="ou saisir manuellement (8-14 chiffres)"
              value={manualEan}
              onChange={e => setManualEan(e.target.value.replace(/\D/g, ''))}
              maxLength={14}
              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#059669] focus:outline-none font-mono"
            />
            <button
              type="submit"
              disabled={isAdding || manualEan.length < 8}
              className="px-3 py-2 text-sm border border-gray-200 rounded-lg text-gray-700 hover:border-[#059669] hover:text-[#059669] disabled:opacity-40"
            >
              Ajouter
            </button>
          </form>
        </div>
      )}
    </div>
  )
}

// ─── Section historique prix (graphique temps × prix) ────────────────────────

function PrixHistorySection({ produitId }: { produitId: number }) {
  const { data = [], isLoading } = useQuery({
    queryKey: ['epicerie-prix-historique', produitId],
    queryFn: () => epicerieApi.getPrixHistorique(produitId),
  })

  // Trier ascendant par date pour le graphique
  const series = [...data]
    .filter(r => r.date)
    .sort((a, b) => a.date.localeCompare(b.date))

  return (
    <div>
      <SectionTitle icon={<History className="h-4 w-4" />}>Historique prix d'achat</SectionTitle>
      {isLoading ? (
        <div className="h-44 rounded-lg bg-gray-100 animate-pulse" />
      ) : series.length === 0 ? (
        <p className="text-xs text-gray-400 italic py-2">Aucun historique de prix enregistré</p>
      ) : (
        <PriceChart points={series} />
      )}
    </div>
  )
}

interface HoverInfo {
  idx: number
  x: number
  y: number
}

function PriceChart({ points }: { points: PrixHistoriqueItem[] }) {
  const [hover, setHover] = useState<HoverInfo | null>(null)
  const width = 640
  const height = 220
  const padding = { top: 12, right: 16, bottom: 32, left: 52 }
  const plotW = width - padding.left - padding.right
  const plotH = height - padding.top - padding.bottom

  const times = points.map(p => new Date(p.date).getTime())
  const minT = Math.min(...times)
  const maxT = Math.max(...times)
  const spanT = Math.max(maxT - minT, 1)

  const allPrices = points.flatMap(p => [p.prix_achat_cts, p.prix_vente_cts])
  const minP = Math.min(...allPrices)
  const maxP = Math.max(...allPrices)
  const padP = Math.max((maxP - minP) * 0.1, 10)
  const yMin = Math.max(0, minP - padP)
  const yMax = maxP + padP
  const spanY = Math.max(yMax - yMin, 1)

  const xOf = (t: number) =>
    padding.left + ((t - minT) / spanT) * plotW
  const yOf = (cts: number) =>
    padding.top + plotH - ((cts - yMin) / spanY) * plotH

  const pathAchat = points
    .map((p, i) => {
      const x = xOf(new Date(p.date).getTime())
      const y = yOf(p.prix_achat_cts)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const pathVente = points
    .map((p, i) => {
      const x = xOf(new Date(p.date).getTime())
      const y = yOf(p.prix_vente_cts)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  // Ticks Y (4 paliers)
  const yTicks = [0, 1, 2, 3, 4].map(i => yMin + (spanY * i) / 4)
  // Ticks X : 4-6 dates espacées
  const nbXTicks = Math.min(6, points.length)
  const xTickIdx = Array.from({ length: nbXTicks }, (_, i) =>
    Math.round((i / Math.max(nbXTicks - 1, 1)) * (points.length - 1))
  )

  const active = hover !== null ? points[hover.idx] : null

  function onMove(e: React.MouseEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    // Trouver le point le plus proche
    let best = 0
    let bestDelta = Infinity
    points.forEach((p, i) => {
      const px = xOf(new Date(p.date).getTime())
      const d = Math.abs(px - x)
      if (d < bestDelta) {
        bestDelta = d
        best = i
      }
    })
    setHover({ idx: best, x: xOf(times[best]), y: yOf(points[best].prix_achat_cts) })
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-auto select-none"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Grille + ticks Y */}
        {yTicks.map((v, i) => {
          const y = yOf(v)
          return (
            <g key={i}>
              <line
                x1={padding.left} x2={width - padding.right}
                y1={y} y2={y}
                stroke="#f3f4f6" strokeWidth="1"
              />
              <text
                x={padding.left - 6} y={y + 3}
                fontSize="10" textAnchor="end" fill="#9ca3af"
              >
                {formatEur(v)}
              </text>
            </g>
          )
        })}

        {/* Ticks X */}
        {xTickIdx.map((idx, i) => {
          const p = points[idx]
          if (!p) return null
          const x = xOf(new Date(p.date).getTime())
          return (
            <text
              key={i}
              x={x} y={height - padding.bottom + 14}
              fontSize="10" textAnchor="middle" fill="#9ca3af"
            >
              {formatDateShort(p.date)}
            </text>
          )
        })}

        {/* Lignes achat + vente */}
        <path d={pathVente} fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeDasharray="3 3" />
        <path d={pathAchat} fill="none" stroke="#059669" strokeWidth="2" />

        {/* Points */}
        {points.map((p, i) => {
          const x = xOf(new Date(p.date).getTime())
          const isActive = hover?.idx === i
          return (
            <circle
              key={i}
              cx={x} cy={yOf(p.prix_achat_cts)}
              r={isActive ? 4 : 2.5}
              fill={isActive ? '#059669' : '#10b981'}
              stroke="#fff" strokeWidth="1"
            />
          )
        })}

        {/* Hover crosshair */}
        {hover !== null && (
          <line
            x1={hover.x} x2={hover.x}
            y1={padding.top} y2={height - padding.bottom}
            stroke="#e5e7eb" strokeWidth="1" strokeDasharray="2 2"
          />
        )}

        {/* Overlay invisible pour capture hover */}
        <rect
          x={padding.left} y={padding.top}
          width={plotW} height={plotH}
          fill="transparent"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        />
      </svg>

      {/* Tooltip */}
      {active && (
        <div
          className="pointer-events-none absolute rounded-md bg-white shadow-md border border-gray-200 px-2.5 py-1.5 text-[11px] leading-tight z-10"
          style={{
            left: `${(hover!.x / width) * 100}%`,
            top: 4,
            transform: 'translateX(-50%)',
            maxWidth: 180,
          }}
        >
          <div className="font-medium text-gray-700">{formatDate(active.date)}</div>
          <div className="flex items-center gap-1.5 text-gray-600">
            <span className="w-2 h-0.5 bg-emerald-600 inline-block rounded" />
            Achat {formatEur(active.prix_achat_cts)}
          </div>
          <div className="flex items-center gap-1.5 text-gray-500">
            <span className="w-2 h-0.5 border-t border-dashed border-slate-400 inline-block" />
            Vente {formatEur(active.prix_vente_cts)}
          </div>
          {active.source_fournisseur && (
            <div className="text-gray-400 mt-0.5">
              {active.source_fournisseur}{active.reference && ` · ${active.reference}`}
            </div>
          )}
        </div>
      )}

      {/* Légende */}
      <div className="mt-2 flex items-center justify-between text-[10px] text-gray-500">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-emerald-600 inline-block rounded" />
            Achat HT
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 border-t border-dashed border-slate-400 inline-block" />
            Vente TTC
          </span>
        </div>
        <span>{points.length} point{points.length > 1 ? 's' : ''}</span>
      </div>
    </div>
  )
}

function formatDateShort(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('fr-FR', { month: '2-digit', year: '2-digit' })
}

// ─── Helpers UI ──────────────────────────────────────────────────────────────

function SectionTitle({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-3">
      {icon}{children}
    </h3>
  )
}
