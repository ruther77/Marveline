import { PageHeader } from '@/components/PageHeader'
import { useState, useMemo, useEffect } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { normalizeError } from '@shared/errors/normalizer'
import { Progress } from '@shared/components/ui'
import {
  ArrowLeft,
  ClipboardCheck,
  Play,
  CheckCircle,
  AlertTriangle,
  Search,
  Save,
  Minus,
  Plus,
  Package,
  TrendingUp,
  TrendingDown,
  Equal,
  BarChart3,
} from 'lucide-react'
import { useActiveInventaire, useInventaireSession, useInventaireMutations } from '@/api/queries/useStock'
import { useProductsList } from '@/api/queries/useProducts'
import { cn } from '@/lib/utils'
import type { CountingEntry } from '@/types/stock_management'

// ── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6 animate-pulse">
      <div className="flex items-center gap-4">
        <div className="w-9 h-9 bg-dark-700 rounded-lg" />
        <div className="space-y-2 flex-1">
          <div className="h-5 bg-dark-700 rounded w-48" />
          <div className="h-3 bg-dark-700 rounded w-32" />
        </div>
      </div>
      <div className="h-2 bg-dark-700 rounded-full" />
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="card p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="h-4 bg-dark-700 rounded w-40" />
            <div className="h-8 w-24 bg-dark-700 rounded-lg" />
          </div>
          <div className="h-3 bg-dark-700 rounded w-24" />
        </div>
      ))}
    </div>
  )
}

// ── Variance card ────────────────────────────────────────────────────────────

function VarianceCard({
  productName,
  expected,
  counted,
  delta,
}: {
  productName: string
  expected: number
  counted: number
  delta: number
}) {
  const isPositive = delta > 0
  const isNegative = delta < 0

  return (
    <div
      className={cn(
        'card p-4 space-y-2 transition-colors border',
        isNegative && 'ring-1 ring-red-700/40 border-red-800/30',
        isPositive && 'ring-1 ring-green-700/30 border-green-800/30',
        !isPositive && !isNegative && 'border-dark-600',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="font-medium truncate flex-1">{productName}</p>
        <span
          className={cn(
            'text-sm font-bold px-2.5 py-0.5 rounded-full border',
            isNegative && 'bg-red-900/40 text-red-300 border-red-700/40',
            isPositive && 'bg-green-900/40 text-green-300 border-green-700/40',
            !isPositive && !isNegative && 'bg-dark-700 text-dark-300 border-dark-600',
          )}
        >
          {isPositive && <TrendingUp className="w-3 h-3 inline mr-1" />}
          {isNegative && <TrendingDown className="w-3 h-3 inline mr-1" />}
          {!isPositive && !isNegative && <Equal className="w-3 h-3 inline mr-1" />}
          {delta > 0 ? '+' : ''}{delta}
        </span>
      </div>
      <div className="flex items-center gap-4 text-xs text-dark-400">
        <span>Attendu : <span className="text-dark-200">{expected}</span></span>
        <span>Compté : <span className="text-dark-200">{counted}</span></span>
      </div>
    </div>
  )
}

// ── Main ─────────────────────────────────────────────────────────────────────

export default function PhysicalInventoryPage() {
  const navigate = useNavigate()
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [counts, setCounts] = useState<Record<number, number>>({})
  const [error, setError] = useState('')
  const [productFilter, setProductFilter] = useState('')

  // Auto-load active session on mount
  const { data: activeSession, isLoading: activeLoading } = useActiveInventaire()
  useEffect(() => {
    if (activeSession && activeSession.status === 'in_progress' && sessionId === null) {
      setSessionId(activeSession.id)
    }
  }, [activeSession, sessionId])

  const { data: session, isLoading: sessionLoading } = useInventaireSession(sessionId)
  const {
    data: productsData,
    isLoading: productsLoading,
    error: productsError,
    refetch: refetchProducts,
  } = useProductsList({ limit: 500 })
  const { start, update, complete } = useInventaireMutations()

  const allProducts = productsData?.items ?? []
  const products = useMemo(() => {
    if (!productFilter) return allProducts
    const q = productFilter.toLowerCase()
    return allProducts.filter(
      (p) => p.name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q),
    )
  }, [allProducts, productFilter])

  const isActive = session?.status === 'in_progress'
  const isCompleted = session?.status === 'completed'
  const variances = session?.variances_json ?? {}
  const varianceEntries = Object.entries(variances)

  // KPI pour session active
  const kpi = useMemo(() => {
    const total = products.length
    const counted = products.filter((p) => counts[p.id] !== undefined && counts[p.id] !== null).length
    return { total, counted, remaining: total - counted }
  }, [products, counts])

  const progressVariant = kpi.counted === kpi.total && kpi.total > 0 ? 'success' : 'default'

  // Variance KPI
  const varianceKpi = useMemo(() => {
    let surplus = 0
    let deficit = 0
    let exact = 0
    for (const v of Object.values(variances)) {
      if (v.delta > 0) surplus++
      else if (v.delta < 0) deficit++
      else exact++
    }
    return { surplus, deficit, exact, total: surplus + deficit + exact }
  }, [variances])

  // ── Handlers ─────────────────────────────────────────────────────────────

  const handleStart = async () => {
    setError('')
    try {
      const s = await start.mutateAsync()
      setSessionId(s.id)
      setCounts({})
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur lors du démarrage.')
    }
  }

  const handleUpdate = async () => {
    if (!sessionId) return
    setError('')
    const entries: CountingEntry[] = Object.entries(counts).map(([id, qty]) => ({
      product_id: Number(id),
      counted_quantity: qty,
    }))
    try {
      await update.mutateAsync({ sessionId, entries })
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur lors de la sauvegarde.')
    }
  }

  const handleComplete = async () => {
    if (!sessionId) return
    setError('')
    try {
      await complete.mutateAsync(sessionId)
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur lors de la validation.')
    }
  }

  const updateCount = (productId: number, delta: number) => {
    setCounts((prev) => {
      const current = prev[productId] ?? 0
      const next = Math.max(0, current + delta)
      return { ...prev, [productId]: next }
    })
  }

  const setCount = (productId: number, value: number) => {
    setCounts((prev) => ({ ...prev, [productId]: Math.max(0, value) }))
  }

  // ── Error state ──────────────────────────────────────────────────────────

  if (productsError) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto p-4 md:p-6">
        <div className="text-center py-12">
          <Package className="w-12 h-12 mx-auto mb-4 text-dark-500 opacity-50" />
          <p className="text-red-400 font-medium mb-2">Erreur de chargement</p>
          <p className="text-dark-400 text-sm mb-6">Impossible de charger la liste des produits.</p>
          <button
            onClick={() => refetchProducts()}
            className="bg-dark-700 hover:bg-dark-600 text-dark-50 text-sm font-medium px-4 py-2 rounded-lg"
          >
            Réessayer
          </button>
        </div>
      </div>
    )
  }

  // ── Loading state ────────────────────────────────────────────────────────

  if (activeLoading || ((sessionLoading || productsLoading) && sessionId)) {
    return (
      <div className="p-4 md:p-6">
        <Skeleton />
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6">
      <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">

        {/* ── Header ────────────────────────────────────────────────────── */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate({ to: '/stock/items' })}
            className="p-2 hover:bg-dark-700 rounded-lg text-dark-400 transition-colors"
            aria-label="Retour"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <ClipboardCheck className="w-5 h-5 text-gold-400 shrink-0" />
              <PageHeader title="Inventaire physique" />
              {isActive && (
                <span className="text-xs px-2 py-0.5 rounded-full font-medium border bg-amber-900/40 text-amber-300 border-amber-700/40">
                  En cours
                </span>
              )}
              {isCompleted && (
                <span className="text-xs px-2 py-0.5 rounded-full font-medium border bg-green-900/40 text-green-300 border-green-700/40">
                  Terminé
                </span>
              )}
            </div>
            {isActive && (
              <p className="text-sm text-dark-400 mt-0.5">
                {kpi.counted}/{kpi.total} produits comptés
              </p>
            )}
          </div>
        </div>

        {/* ── Error banner ──────────────────────────────────────────────── */}
        {error && (
          <div className="flex items-center gap-3 bg-red-900/20 border border-red-700/40 rounded-xl p-4">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {/* ── Empty state: no session ───────────────────────────────────── */}
        {!sessionId && !isCompleted && (
          <div className="space-y-6">
            <div className="card text-center py-16 space-y-4">
              <div className="w-16 h-16 mx-auto bg-gold-500/10 rounded-2xl flex items-center justify-center">
                <ClipboardCheck className="w-8 h-8 text-gold-400" />
              </div>
              <div>
                <p className="font-semibold text-lg">Aucun inventaire en cours</p>
                <p className="text-dark-400 text-sm mt-1 max-w-xs mx-auto">
                  Lancez une session pour compter physiquement vos articles et détecter les écarts.
                </p>
              </div>
            </div>
            <button
              onClick={handleStart}
              disabled={start.isPending}
              className="w-full flex items-center justify-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-semibold py-4 rounded-xl disabled:opacity-50 transition-colors"
            >
              <Play className="w-5 h-5" />
              {start.isPending ? 'Démarrage…' : 'Démarrer un inventaire'}
            </button>
          </div>
        )}

        {/* ── Session completed: variances ──────────────────────────────── */}
        {isCompleted && (
          <div className="space-y-6">
            {/* Success banner */}
            <div className="flex items-center gap-3 bg-green-900/20 border border-green-700/40 rounded-xl p-4">
              <CheckCircle className="w-5 h-5 text-green-400 shrink-0" />
              <div className="text-sm">
                <p className="text-green-300 font-medium">Inventaire terminé</p>
                <p className="text-green-400/80 text-xs mt-0.5">
                  {varianceEntries.length} produit{varianceEntries.length > 1 ? 's' : ''} analysé{varianceEntries.length > 1 ? 's' : ''}
                </p>
              </div>
            </div>

            {/* Variance KPIs */}
            {varianceEntries.length > 0 && (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div className="card p-3 text-center">
                    <p className="text-2xl font-bold text-green-400">{varianceKpi.exact}</p>
                    <p className="text-xs text-dark-400 mt-1">Conformes</p>
                  </div>
                  <div className="card p-3 text-center">
                    <p className="text-2xl font-bold text-red-400">{varianceKpi.deficit}</p>
                    <p className="text-xs text-dark-400 mt-1">Déficits</p>
                  </div>
                  <div className="card p-3 text-center">
                    <p className="text-2xl font-bold text-amber-400">{varianceKpi.surplus}</p>
                    <p className="text-xs text-dark-400 mt-1">Surplus</p>
                  </div>
                </div>

                {/* Variance cards */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-dark-400" />
                    <p className="text-sm font-medium text-dark-300">Détail des écarts</p>
                  </div>
                  {varianceEntries.map(([id, v]) => {
                    const product = allProducts.find((p) => String(p.id) === id)
                    return (
                      <VarianceCard
                        key={id}
                        productName={product?.name ?? `Produit #${id}`}
                        expected={v.expected}
                        counted={v.counted}
                        delta={v.delta}
                      />
                    )
                  })}
                </div>
              </>
            )}

            {/* New session CTA */}
            <button
              onClick={() => {
                setSessionId(null)
                setCounts({})
              }}
              className="w-full flex items-center justify-center gap-2 bg-dark-700 hover:bg-dark-600 text-dark-50 font-semibold py-4 rounded-xl transition-colors"
            >
              <Play className="w-5 h-5" />
              Nouvel inventaire
            </button>
          </div>
        )}

        {/* ── Active session: counting ──────────────────────────────────── */}
        {isActive && !productsLoading && (
          <div className="space-y-4">
            {/* Progress */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-dark-400">
                <span className="flex items-center gap-1.5">
                  <ClipboardCheck className="w-3.5 h-3.5" />
                  {kpi.counted}/{kpi.total} produits comptés
                </span>
                {kpi.remaining > 0 && (
                  <span className="text-amber-400 font-medium">
                    {kpi.remaining} restant{kpi.remaining > 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <Progress
                value={kpi.counted}
                max={kpi.total}
                variant={progressVariant as 'default' | 'success'}
                size="sm"
              />
            </div>

            {/* Alert */}
            <div className="flex items-start gap-3 bg-amber-900/20 border border-amber-700/40 rounded-xl p-4">
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="text-amber-300 font-medium">Session en cours</p>
                <p className="text-amber-400/80 text-xs mt-0.5">
                  Saisissez les quantités physiques comptées pour chaque article.
                </p>
              </div>
            </div>

            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
              <input
                type="text"
                placeholder="Rechercher par nom ou référence…"
                value={productFilter}
                onChange={(e) => setProductFilter(e.target.value)}
                className="input w-full pl-10"
              />
            </div>

            {/* Product cards */}
            <div className="space-y-3">
              {products.length === 0 && productFilter && (
                <div className="text-center py-8 text-dark-400">
                  <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">Aucun produit trouvé pour « {productFilter} »</p>
                </div>
              )}

              {products.map((p) => {
                const count = counts[p.id]
                const isCounted = count !== undefined && count !== null
                return (
                  <div
                    key={p.id}
                    className={cn(
                      'card p-4 space-y-3 transition-all',
                      isCounted && 'ring-1 ring-green-500/30',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{p.name}</p>
                        <p className="text-dark-400 text-xs mt-0.5">Réf. {p.sku}</p>
                      </div>
                      {isCounted && (
                        <CheckCircle className="w-4 h-4 text-green-400 shrink-0" />
                      )}
                    </div>

                    {/* Counter */}
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => updateCount(p.id, -1)}
                        className="w-12 h-12 card border border-dark-600 flex items-center justify-center text-lg font-bold hover:bg-dark-600 active:scale-95 transition-all rounded-xl"
                        aria-label="Diminuer"
                      >
                        <Minus className="w-4 h-4" />
                      </button>
                      <div className="flex-1">
                        <input
                          type="number"
                          min={0}
                          value={count ?? ''}
                          onChange={(e) => {
                            const val = e.target.value
                            if (val === '') {
                              setCounts((prev) => {
                                const next = { ...prev }
                                delete next[p.id]
                                return next
                              })
                            } else {
                              setCount(p.id, parseInt(val) || 0)
                            }
                          }}
                          placeholder="Qté"
                          className="input w-full text-center text-lg font-semibold py-2.5"
                        />
                      </div>
                      <button
                        onClick={() => updateCount(p.id, 1)}
                        className="w-12 h-12 card border border-dark-600 flex items-center justify-center text-lg font-bold hover:bg-dark-600 active:scale-95 transition-all rounded-xl"
                        aria-label="Augmenter"
                      >
                        <Plus className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Action buttons */}
            <div className="space-y-3 pt-2">
              <button
                onClick={handleComplete}
                disabled={complete.isPending || kpi.counted === 0}
                className="w-full flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 text-white font-semibold py-4 rounded-xl disabled:opacity-50 transition-colors"
              >
                <CheckCircle className="w-5 h-5" />
                {complete.isPending ? 'Validation…' : 'Valider l\'inventaire'}
              </button>
              <button
                onClick={handleUpdate}
                disabled={update.isPending || kpi.counted === 0}
                className="w-full flex items-center justify-center gap-2 bg-dark-700 hover:bg-dark-600 text-dark-50 font-semibold py-4 rounded-xl disabled:opacity-50 transition-colors"
              >
                <Save className="w-5 h-5" />
                {update.isPending ? 'Sauvegarde…' : 'Sauvegarder le brouillon'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
