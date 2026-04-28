import { useState, useRef, useEffect } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { QrCode, Search, ArrowLeft, Keyboard, X, History, Package, Truck, RotateCcw, FileText, User, Calendar, Loader2 } from 'lucide-react'
import { QRScanner } from '@shared/components/ui/QRScanner'
import { useResolveQr } from '@/api/queries/useOperations'
import { searchApi } from '@/api/search'
import { useDebounce } from '@/hooks/useDebounce'
import { cn } from '@/lib/utils'
import type { SearchResult, SearchResultType } from '@/types/search'

// ── QR parsing (formats connus) ──────────────────────────────────────────────

function parseQrCode(value: string): { type: 'reservation' | 'product' | 'departure' | 'return'; id: number } | null {
  const m1 = value.match(/^(reservation|product|departure|return):(\d+)$/)
  if (m1) return { type: m1[1] as 'reservation' | 'product' | 'departure' | 'return', id: parseInt(m1[2], 10) }
  const trimmed = value.trim()
  const rawId = parseInt(trimmed, 10)
  if (!isNaN(rawId) && String(rawId) === trimmed) return { type: 'reservation', id: rawId }
  return null
}

// ── Scans récents (localStorage) ─────────────────────────────────────────────

interface RecentEntry { label: string; type: string; url: string; at: string }
const STORAGE_KEY = 'qr_recent_scans_v2'
const MAX_RECENT = 8

function loadRecent(): RecentEntry[] {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') } catch { return [] }
}
function saveRecent(entries: RecentEntry[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
}
function addRecent(entry: Omit<RecentEntry, 'at'>) {
  const all = loadRecent()
  const updated = [{ ...entry, at: new Date().toISOString() }, ...all.filter(e => e.url !== entry.url)].slice(0, MAX_RECENT)
  saveRecent(updated)
  return updated
}

// ── Type icons ───────────────────────────────────────────────────────────────

const TYPE_ICON: Record<SearchResultType, typeof Package> = {
  reservation: Calendar,
  customer: User,
  product: Package,
  invoice: FileText,
  devis: FileText,
}

const TYPE_COLOR: Record<SearchResultType, string> = {
  reservation: 'text-blue-400 bg-blue-500/10',
  customer: 'text-purple-400 bg-purple-500/10',
  product: 'text-green-400 bg-green-500/10',
  invoice: 'text-amber-400 bg-amber-500/10',
  devis: 'text-orange-400 bg-orange-500/10',
}

const TYPE_LABEL: Record<SearchResultType, string> = {
  reservation: 'Réservation',
  customer: 'Client',
  product: 'Produit',
  invoice: 'Facture',
  devis: 'Devis',
}

// ── Main ─────────────────────────────────────────────────────────────────────

export default function ScanPage() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [recent, setRecent] = useState<RecentEntry[]>(() => loadRecent())

  const debouncedQuery = useDebounce(query, 250)
  const resolveQr = useResolveQr()

  // Recherche globale
  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 2) {
      setResults([])
      return
    }
    let cancelled = false
    setSearching(true)
    searchApi.search(debouncedQuery, ['reservation', 'customer', 'product', 'invoice', 'devis'], 10)
      .then((data) => { if (!cancelled) setResults(data.results) })
      .catch(() => { if (!cancelled) setResults([]) })
      .finally(() => { if (!cancelled) setSearching(false) })
    return () => { cancelled = true }
  }, [debouncedQuery])

  // Autofocus
  useEffect(() => { inputRef.current?.focus() }, [])

  const navigateToResult = (r: SearchResult) => {
    setRecent(addRecent({ label: r.title, type: r.type, url: r.url }))
    setQuery('')
    setResults([])

    if (r.type === 'reservation') {
      navigate({ to: '/reservations/$id', params: { id: String(r.id) } })
    } else if (r.type === 'customer') {
      navigate({ to: '/customers/$id', params: { id: String(r.id) } })
    } else if (r.type === 'product') {
      navigate({ to: '/catalogue/products/$id', params: { id: String(r.id) } })
    } else if (r.type === 'invoice') {
      navigate({ to: '/finance/invoices/$id', params: { id: String(r.id) } })
    } else if (r.type === 'devis') {
      navigate({ to: '/devis/$id', params: { id: String(r.id) } })
    }
  }

  const handleQrScan = (value: string) => {
    setScanning(false)
    const parsed = parseQrCode(value)
    if (parsed) {
      const label = `${parsed.type === 'product' ? 'Produit' : 'Réservation'} #${parsed.id}`
      setRecent(addRecent({ label, type: parsed.type, url: `/${parsed.type}/${parsed.id}` }))

      if (parsed.type === 'departure') {
        navigate({ to: '/operations/departure/$reservationId', params: { reservationId: String(parsed.id) } })
      } else if (parsed.type === 'return') {
        navigate({ to: '/operations/return/$reservationId', params: { reservationId: String(parsed.id) } })
      } else if (parsed.type === 'product') {
        navigate({ to: '/catalogue/products/$id', params: { id: String(parsed.id) } })
      } else {
        navigate({ to: '/reservations/$id', params: { id: String(parsed.id) } })
      }
      return
    }

    // Fallback backend
    resolveQr.mutate(value, {
      onSuccess: (qr) => {
        setRecent(addRecent({ label: qr.product_name || `Article #${qr.stock_item_id}`, type: 'product', url: `/catalogue/products/${qr.product_id}` }))
        navigate({ to: '/catalogue/products/$id', params: { id: String(qr.product_id) } })
      },
      onError: () => {
        setQuery(value)
        inputRef.current?.focus()
      },
    })
  }

  const navigateRecent = (entry: RecentEntry) => {
    navigate({ to: entry.url as never })
  }

  const clearRecent = () => {
    saveRecent([])
    setRecent([])
  }

  const hasResults = results.length > 0
  const showRecent = !query && recent.length > 0

  return (
    <div className="max-w-lg mx-auto space-y-4 pb-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate({ to: '/operations' })}
          className="p-2 hover:bg-dark-700/30 rounded-lg text-dark-400 min-h-[44px] min-w-[44px] flex items-center justify-center"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-bold flex-1">Recherche rapide</h1>
        <button
          onClick={() => setScanning(true)}
          className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-gold-500 hover:bg-gold-600 text-dark-900 rounded-lg"
        >
          <QrCode className="w-4 h-4" />
          Scanner
        </button>
      </div>

      {/* Search input — toujours visible */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Réf, nom client, produit, n° facture..."
          className="input w-full pl-12 pr-10 py-3.5 text-base rounded-xl"
          autoComplete="off"
        />
        {query && (
          <button
            onClick={() => { setQuery(''); setResults([]); inputRef.current?.focus() }}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-dark-400 hover:text-dark-200"
          >
            <X className="w-4 h-4" />
          </button>
        )}
        {searching && (
          <Loader2 className="absolute right-10 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400 animate-spin" />
        )}
      </div>

      {/* Résultats */}
      {hasResults && (
        <div className="card p-0 overflow-hidden divide-y divide-dark-200/10 dark:divide-dark-700/50">
          {results.map((r) => {
            const Icon = TYPE_ICON[r.type] || Package
            const color = TYPE_COLOR[r.type] || 'text-dark-400 bg-dark-100/10'
            return (
              <button
                key={`${r.type}-${r.id}`}
                onClick={() => navigateToResult(r)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-dark-800/60 transition-colors text-left"
              >
                <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center shrink-0', color)}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{r.title}</p>
                  {r.subtitle && <p className="text-xs text-dark-400 truncate">{r.subtitle}</p>}
                </div>
                <span className="text-[10px] text-dark-500 shrink-0 uppercase">{TYPE_LABEL[r.type]}</span>
              </button>
            )
          })}
        </div>
      )}

      {/* Aucun résultat */}
      {query.length >= 2 && !searching && results.length === 0 && (
        <div className="card text-center py-8">
          <Search className="w-6 h-6 text-dark-500 mx-auto mb-2" />
          <p className="text-sm text-dark-400">Aucun résultat pour "{query}"</p>
          <p className="text-xs text-dark-500 mt-1">Essayez une référence, un nom ou un numéro</p>
        </div>
      )}

      {/* Raccourcis rapides */}
      {!query && (
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => navigate({ to: '/operations' })}
            className="card p-4 flex items-center gap-3 hover:shadow-md transition-shadow text-left"
          >
            <Truck className="w-5 h-5 text-orange-400" />
            <div>
              <p className="text-sm font-medium">Départs</p>
              <p className="text-[11px] text-dark-400">Opérations du jour</p>
            </div>
          </button>
          <button
            onClick={() => navigate({ to: '/operations' })}
            className="card p-4 flex items-center gap-3 hover:shadow-md transition-shadow text-left"
          >
            <RotateCcw className="w-5 h-5 text-blue-400" />
            <div>
              <p className="text-sm font-medium">Retours</p>
              <p className="text-[11px] text-dark-400">Retours en attente</p>
            </div>
          </button>
        </div>
      )}

      {/* Récents */}
      {showRecent && (
        <div className="card p-0 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-dark-700/50">
            <div className="flex items-center gap-2 text-dark-400">
              <History className="w-4 h-4" />
              <span className="text-xs font-medium">Récents</span>
            </div>
            <button onClick={clearRecent} className="text-[11px] text-dark-500 hover:text-dark-300">
              Effacer
            </button>
          </div>
          {recent.map((entry, i) => (
            <button
              key={i}
              onClick={() => navigateRecent(entry)}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-dark-800/60 transition-colors text-left"
            >
              <span className="text-xs text-dark-500 capitalize shrink-0 w-16">{TYPE_LABEL[entry.type as SearchResultType] || entry.type}</span>
              <span className="text-sm truncate flex-1">{entry.label}</span>
              <span className="text-[10px] text-dark-600 shrink-0">
                {new Date(entry.at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Scanner QR overlay */}
      {scanning && (
        <div className="fixed inset-0 z-50 bg-black">
          <div className="relative w-full h-full">
            <QRScanner
              active
              mode="scan"
              onScan={handleQrScan}
              onError={() => setScanning(false)}
            />
            {/* Overlay corners */}
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute top-1/4 left-1/4 w-10 h-10 border-t-2 border-l-2 border-gold-400" />
              <div className="absolute top-1/4 right-1/4 w-10 h-10 border-t-2 border-r-2 border-gold-400" />
              <div className="absolute bottom-1/4 left-1/4 w-10 h-10 border-b-2 border-l-2 border-gold-400" />
              <div className="absolute bottom-1/4 right-1/4 w-10 h-10 border-b-2 border-r-2 border-gold-400" />
            </div>
            <button
              onClick={() => setScanning(false)}
              className="absolute top-6 right-6 p-3 bg-black/50 rounded-full text-white z-10"
            >
              <X className="w-6 h-6" />
            </button>
            <p className="absolute bottom-16 left-0 right-0 text-center text-white/70 text-sm">
              Pointez vers un QR code
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
