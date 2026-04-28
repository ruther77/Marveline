import { useState, useMemo, useRef } from 'react'
import { useParams, useNavigate, Link } from '@tanstack/react-router'
import {
  Package, Camera, Plus, Star, Trash2, ChevronLeft, ChevronRight,
  Layers, Calendar, Shield, Wrench, History,
  ChevronDown, Pencil, ExternalLink,
} from 'lucide-react'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { StockLevelBar } from '@shared/components/ui'
import { cn, formatDate } from '@/lib/utils'
import {
  useProductDetail, useProductImages, useProductAvailability,
  useProductStock, useProductAudit,
  useAddProductImage, useDeleteProductImage, useSetPrimaryImage,
} from '@/api/queries'
import { useProductVariantsList } from '@/api/queries/useProductVariants'
import type { ProductAvailabilitySlot } from '@/types/product'
import type { ProductStockDetail } from '@/types'
import { STOCK_ITEM_STATUS_LABELS, STOCK_ITEM_STATUS_COLORS } from '@/lib/constants'

// ── Helpers ──────────────────────────────────────────────────────────────────

function toYMD(d: Date): string { return d.toISOString().slice(0, 10) }
function addDays(d: Date, n: number): Date { const r = new Date(d); r.setDate(r.getDate() + n); return r }

type StatusKey = keyof typeof STOCK_ITEM_STATUS_LABELS

// ── Section wrapper ──────────────────────────────────────────────────────────

function Section({ title, icon, children, action, defaultOpen = true }: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
  action?: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="card p-4 space-y-3">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 text-left group"
      >
        <span className="text-dark-400">{icon}</span>
        <span className="text-sm font-semibold flex-1">{title}</span>
        {action && <span onClick={(e) => e.stopPropagation()}>{action}</span>}
        <ChevronDown className={cn('w-4 h-4 text-dark-500 transition-transform', open && 'rotate-180')} />
      </button>
      {open && <div className="space-y-3">{children}</div>}
    </div>
  )
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6 animate-pulse">
      <div className="h-52 bg-dark-700 rounded-2xl" />
      <div className="space-y-2">
        <div className="h-5 bg-dark-700 rounded w-2/3" />
        <div className="h-3 bg-dark-700 rounded w-1/3" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {[0, 1, 2].map((i) => <div key={i} className="h-20 bg-dark-700 rounded-xl" />)}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {[0, 1, 2].map((i) => <div key={i} className="aspect-square bg-dark-700 rounded-xl" />)}
      </div>
    </div>
  )
}

// ── Mini calendar ────────────────────────────────────────────────────────────

function MiniCalendar({ productId, stockQty }: { productId: number; stockQty: number }) {
  const today = useMemo(() => new Date(), [])
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth())

  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const dateFrom = toYMD(firstDay)
  const dateTo = toYMD(lastDay)

  const { data: availability } = useProductAvailability(productId, dateFrom, dateTo)
  const slots = availability?.busy_slots ?? []

  const startDow = (firstDay.getDay() + 6) % 7
  const daysInMonth = lastDay.getDate()
  const todayYMD = toYMD(today)

  const getReserved = (day: number): number => {
    const d = toYMD(new Date(year, month, day))
    return slots
      .filter((s: ProductAvailabilitySlot) => s.date_from <= d && s.date_to >= d)
      .reduce((acc: number, s: ProductAvailabilitySlot) => acc + s.reserved_quantity, 0)
  }

  const prev = () => { if (month === 0) { setMonth(11); setYear(y => y - 1) } else setMonth(m => m - 1) }
  const next = () => { if (month === 11) { setMonth(0); setYear(y => y + 1) } else setMonth(m => m + 1) }

  const monthLabel = new Date(year, month).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
  const DAYS = ['L', 'M', 'M', 'J', 'V', 'S', 'D']

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <button onClick={prev} className="p-1 hover:bg-dark-700 rounded"><ChevronLeft className="w-4 h-4 text-dark-400" /></button>
        <span className="text-sm font-medium capitalize">{monthLabel}</span>
        <button onClick={next} className="p-1 hover:bg-dark-700 rounded"><ChevronRight className="w-4 h-4 text-dark-400" /></button>
      </div>
      <div className="grid grid-cols-7 gap-0.5 text-center">
        {DAYS.map((d, i) => <span key={i} className="text-[10px] text-dark-500 py-1">{d}</span>)}
        {Array.from({ length: startDow }).map((_, i) => <span key={`e${i}`} />)}
        {Array.from({ length: daysInMonth }).map((_, i) => {
          const day = i + 1
          const ymd = toYMD(new Date(year, month, day))
          const reserved = getReserved(day)
          const ratio = stockQty > 0 ? reserved / stockQty : 0
          const isPast = ymd < todayYMD
          const isToday = ymd === todayYMD

          return (
            <div
              key={day}
              className={cn(
                'aspect-square flex flex-col items-center justify-center rounded-lg text-[11px] relative',
                isPast && 'opacity-30',
                isToday && 'ring-1 ring-primary-500',
                !isPast && ratio === 0 && 'text-dark-300',
                !isPast && ratio > 0 && ratio < 0.7 && 'bg-amber-500/10 text-amber-400',
                !isPast && ratio >= 0.7 && 'bg-red-500/10 text-red-400',
              )}
            >
              <span className="font-medium">{day}</span>
              {!isPast && reserved > 0 && (
                <span className="text-[8px] leading-none">{reserved}</span>
              )}
            </div>
          )
        })}
      </div>
      <div className="flex items-center gap-3 text-[10px] text-dark-500 justify-center">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-dark-700" /> Libre</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-amber-500/30" /> Partiel</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-red-500/30" /> Complet</span>
      </div>
    </div>
  )
}

// ── Main ─────────────────────────────────────────────────────────────────────

export default function ProductDetailPage() {
  const { id } = useParams({ strict: false })
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const productId = id ? parseInt(id, 10) : null

  // Data
  const { data: product, isLoading, error, refetch } = useProductDetail(productId)
  const { data: images } = useProductImages(productId)
  const { data: variants } = useProductVariantsList(productId)
  const { data: stockDetail } = useProductStock(productId)
  const { data: auditLogs } = useProductAudit(productId)

  // Photo mutations
  const addImage = useAddProductImage(productId ?? 0)
  const deleteImage = useDeleteProductImage(productId ?? 0)
  const setPrimary = useSetPrimaryImage(productId ?? 0)

  // State
  const [stockFilter, setStockFilter] = useState<string | null>(null)

  const stockItems = useMemo(() => {
    const items = stockDetail?.items ?? []
    if (!stockFilter) return items
    return items.filter((i) => i.status === stockFilter)
  }, [stockDetail, stockFilter])
  const hasTrackedUnits = (stockDetail?.items?.length ?? 0) > 0

  if (isLoading) return <div className="p-4 md:p-6"><PageSkeleton /></div>
  if (error) return <div className="p-4 md:p-6 max-w-2xl lg:max-w-5xl mx-auto"><ErrorState onRetry={() => refetch()} /></div>
  if (!product) return null

  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) addImage.mutate(file)
    e.target.value = ''
  }

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-5">

      {/* ── Hero ────────────────────────────────────────────────── */}
      <div className="card rounded-2xl overflow-hidden">
        {product.image_url ? (
          <img src={product.image_url} alt={product.name} className="w-full h-52 object-cover" />
        ) : (
          <div className="w-full h-52 bg-dark-950 flex items-center justify-center">
            <Package className="w-16 h-16 text-dark-500" />
          </div>
        )}
      </div>

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-lg font-bold truncate">{product.name}</h1>
          <p className="text-xs text-dark-400 font-mono">Réf. {product.sku}</p>
        </div>
        <span className={cn(
          'text-xs px-2.5 py-1 rounded-full font-medium border shrink-0',
          product.available_quantity === 0
            ? 'bg-red-500/10 text-red-400 border-red-500/20'
            : 'bg-green-500/10 text-green-400 border-green-500/20',
        )}>
          {product.available_quantity} dispo
        </span>
      </div>

      {/* KPIs compacts */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        <div className="card p-3 text-center">
          <p className="text-lg font-bold">{product.price_per_day_euros.toFixed(2)} €</p>
          <p className="text-[10px] text-dark-400">/ jour</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-lg font-bold">{product.stock_quantity}</p>
          <p className="text-[10px] text-dark-400">Stock total</p>
        </div>
        <div className="card p-3 text-center">
          <p className={cn('text-lg font-bold', product.available_quantity === 0 ? 'text-red-400' : 'text-green-400')}>
            {product.available_quantity}
          </p>
          <p className="text-[10px] text-dark-400">Disponible</p>
        </div>
      </div>

      {/* ── Photos ──────────────────────────────────────────────── */}
      <Section
        title="Photos"
        icon={<Camera className="w-4 h-4" />}
        action={
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-1 hover:bg-dark-700 rounded text-dark-400"
          >
            <Plus className="w-4 h-4" />
          </button>
        }
      >
        <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handlePhotoUpload} />
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {/* Afficher image_url du produit si aucune image uploadée ne la contient */}
          {product.image_url && !(images ?? []).some((img) => img.url === product.image_url) && (
            <div className="aspect-square rounded-xl overflow-hidden bg-dark-700 relative">
              <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
              <span className="absolute top-1.5 left-1.5 text-[10px] bg-dark-600 text-dark-300 px-1.5 py-0.5 rounded-full font-medium">
                Catalogue
              </span>
            </div>
          )}
          {(images ?? []).map((img) => (
            <div key={img.id} className="aspect-square rounded-xl overflow-hidden bg-dark-700 relative group">
              <img src={img.url} alt="" className="w-full h-full object-cover" />
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                {!img.is_primary && (
                  <button onClick={() => setPrimary.mutate(img.id)} className="p-1.5 bg-dark-900/80 rounded-lg" title="Définir principale">
                    <Star className="w-4 h-4 text-gold-400" />
                  </button>
                )}
                <button onClick={() => deleteImage.mutate(img.id)} className="p-1.5 bg-dark-900/80 rounded-lg" title="Supprimer">
                  <Trash2 className="w-4 h-4 text-red-400" />
                </button>
              </div>
              {img.is_primary && (
                <span className="absolute top-1.5 left-1.5 text-[10px] bg-gold-500 text-dark-900 px-1.5 py-0.5 rounded-full font-medium">
                  Principale
                </span>
              )}
            </div>
          ))}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="aspect-square rounded-xl border border-dashed border-dark-500 flex flex-col items-center justify-center gap-1 text-dark-500 hover:border-dark-400 hover:text-dark-400 transition-colors"
          >
            <Plus className="w-5 h-5" />
            <span className="text-[10px]">Ajouter</span>
          </button>
        </div>
      </Section>

      {/* ── Variantes ───────────────────────────────────────────── */}
      {(variants ?? []).length > 0 && (
        <Section title={`Variantes (${(variants ?? []).length})`} icon={<Layers className="w-4 h-4" />}>
          <div className="space-y-2">
            {(variants ?? []).map((v) => (
              <div key={v.id} className="card p-3 flex items-center gap-3">
                {v.color && (
                  <div className="w-6 h-6 rounded-full border border-dark-600 shrink-0" style={{ backgroundColor: v.color }} />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{v.label}</p>
                  <p className="text-[11px] text-dark-400">{v.sku} · {v.available_quantity}/{v.stock_quantity}</p>
                </div>
                {v.price_per_day != null && (
                  <span className="text-xs text-dark-300 font-medium">{(v.price_per_day / 100).toFixed(2)} €</span>
                )}
                <StockLevelBar available={v.available_quantity} total={v.stock_quantity} size="sm" />
              </div>
            ))}
          </div>
          <Link
            to="/catalogue/products/$id/variants"
            params={{ id: String(id) }}
            className="flex items-center gap-1.5 text-xs text-primary-400 hover:text-primary-300 pt-1"
          >
            <Pencil className="w-3 h-3" /> Gérer les variantes
          </Link>
        </Section>
      )}

      {/* ── Disponibilité ───────────────────────────────────────── */}
      <Section title="Disponibilité" icon={<Calendar className="w-4 h-4" />}>
        <MiniCalendar productId={productId!} stockQty={product.stock_quantity} />
      </Section>

      {/* ── État du parc ────────────────────────────────────────── */}
      <Section title="État du parc" icon={<Shield className="w-4 h-4" />} defaultOpen={false}>
        {stockDetail && (
          <>
            <div className="flex flex-wrap gap-1.5">
              {(['available', 'reserved', 'on_location', 'damaged', 'in_repair', 'retired'] as StatusKey[]).map((status) => {
                const count = stockDetail[`qty_${status}` as keyof ProductStockDetail] as number
                if (count === 0 && status !== 'available') return null
                return (
                  <button
                    key={status}
                    onClick={() => setStockFilter(stockFilter === status ? null : status)}
                    className={cn(
                      'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium transition-all',
                      stockFilter === status
                        ? 'ring-1 ring-primary-500'
                        : '',
                      STOCK_ITEM_STATUS_COLORS[status],
                    )}
                  >
                    {count} {STOCK_ITEM_STATUS_LABELS[status]}
                  </button>
                )
              })}
            </div>
            {stockItems.length > 0 && (
              <div className="space-y-1">
                {stockItems.slice(0, 10).map((item) => (
                  <div key={item.id} className="flex items-center gap-2 py-1.5 px-2 rounded-lg hover:bg-dark-700/50 text-xs">
                    <span className="text-dark-500 font-mono">#{item.id}</span>
                    {item.serial_number && <span className="text-dark-300 font-mono truncate">{item.serial_number}</span>}
                    <span className="flex-1" />
                    <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium', STOCK_ITEM_STATUS_COLORS[item.status as StatusKey])}>
                      {STOCK_ITEM_STATUS_LABELS[item.status as StatusKey] ?? item.status}
                    </span>
                    <Link
                      to="/stock/items/$id"
                      params={{ id: `${product.id}-${item.id}` }}
                      className="inline-flex items-center gap-1 rounded-lg border border-dark-600 px-2 py-1 text-[11px] font-medium text-dark-300 transition-colors hover:bg-dark-700"
                    >
                      <ExternalLink className="w-3 h-3" />
                      Voir unité
                    </Link>
                  </div>
                ))}
                {stockItems.length > 10 && (
                  <p className="text-[11px] text-dark-500 text-center pt-1">+{stockItems.length - 10} unités</p>
                )}
              </div>
            )}
            {stockDetail.total > 0 && !hasTrackedUnits && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
                Suivi unitaire non initialisé pour ce produit. Les compteurs affichés viennent du stock agrégé,
                donc aucun détail d&apos;unité n&apos;est encore disponible.
              </div>
            )}
          </>
        )}
      </Section>


      {/* ── Historique ──────────────────────────────────────────── */}
      <Section title="Historique" icon={<History className="w-4 h-4" />} defaultOpen={false}>
        {(auditLogs ?? []).length === 0 ? (
          <p className="text-xs text-dark-500 py-4 text-center">Aucun événement</p>
        ) : (
          <div className="space-y-2">
            {(auditLogs ?? []).slice(0, 8).map((log) => (
              <div key={log.id} className="flex items-start gap-2 text-xs">
                <span className={cn(
                  'px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 mt-0.5',
                  log.action === 'CREATE' ? 'bg-green-500/10 text-green-400' :
                  log.action === 'DELETE' ? 'bg-red-500/10 text-red-400' :
                  'bg-blue-500/10 text-blue-400',
                )}>
                  {log.action}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-dark-300 truncate">{log.description || 'Modification'}</p>
                  <p className="text-dark-500 text-[10px]">{formatDate(log.created_at)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* ── Actions ─────────────────────────────────────────────── */}
      <div className="space-y-2 pt-2 pb-8">
        <button
          onClick={() => navigate({ to: '/catalogue/products/$id/editor', params: { id: String(id) } })}
          className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl bg-primary-500 text-white text-sm font-semibold hover:bg-primary-500/90 transition-colors"
        >
          <Pencil className="w-4 h-4" />
          Modifier la fiche
        </button>
        <button
          onClick={() => navigate({ to: '/catalogue/products/$id/maintenance', params: { id: String(id) } })}
          className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl border border-dark-600 text-dark-300 text-sm font-medium hover:bg-dark-700 transition-colors"
        >
          <Wrench className="w-4 h-4" />
          Maintenance
        </button>
      </div>
    </div>
  )
}
