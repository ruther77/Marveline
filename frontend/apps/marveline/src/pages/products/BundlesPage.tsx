import { PageHeader } from '@/components/PageHeader'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useBundlesList, useUpdateBundle } from '@/api/queries'
import { useMultiModal } from '@/hooks/useModal'
import { BundleFormModal, BundleDeleteModal } from './components'
import { NoData, ErrorState } from '@shared/components/ui/EmptyState'
import type { Bundle } from '@/types/product'
import { cn, formatCents } from '@/lib/utils'
import { Package, Plus, GripVertical, Star, Eye, EyeOff } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'

// ── Skeleton ──────────────────────────────────────────────────────────────

function PackCardSkeleton() {
  return (
    <div className="flex gap-3 p-4 card border border-dark-600 animate-pulse">
      <div className="w-6 h-6 skel rounded shrink-0 self-center" />
      <div className="w-20 h-20 skel rounded-xl shrink-0" />
      <div className="flex-1 space-y-2 py-1">
        <div className="h-3 skel rounded w-3/4" />
        <div className="h-2 skel rounded w-1/2" />
        <div className="h-4 skel rounded w-20 mt-4" />
      </div>
    </div>
  )
}

// ── Pack card ─────────────────────────────────────────────────────────────

function PackCard({
  bundle,
  onEdit,
  onDelete,
  dragHandleProps,
  isDragging,
}: {
  bundle: Bundle
  onEdit: (b: Bundle) => void
  onDelete: (b: Bundle) => void
  dragHandleProps: React.HTMLAttributes<HTMLDivElement>
  isDragging: boolean
}) {
  const navigate = useNavigate()

  return (
    <article
      className={cn(
        'flex gap-3 p-4 card transition-all',
        isDragging ? 'opacity-50 shadow-xl ring-2 ring-gold-500/30' : 'hover:shadow-md cursor-pointer',
        !bundle.is_active && 'opacity-60',
      )}
      onClick={() => navigate({ to: '/catalogue/bundles/$id', params: { id: String(bundle.id) } })}
    >
      {/* Drag handle */}
      <div
        {...dragHandleProps}
        className="flex items-center self-stretch px-0.5 text-dark-700 hover:text-dark-400 cursor-grab active:cursor-grabbing shrink-0"
        onClick={(e) => e.stopPropagation()}
      >
        <GripVertical className="w-4 h-4" />
      </div>

      {/* Thumb */}
      <div className="w-20 h-20 rounded-xl overflow-hidden bg-dark-950 shrink-0 flex items-center justify-center">
        {bundle.image_url ? (
          <img src={bundle.image_url} alt={bundle.name} className="w-full h-full object-cover" />
        ) : (
          <Package className="w-6 h-6 text-dark-400" />
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 min-w-0">
          <p className="font-semibold text-sm truncate">{bundle.name}</p>
          {bundle.featured && (
            <Star className="w-3 h-3 text-amber-400 fill-amber-400 shrink-0" />
          )}
          {!bundle.is_active && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-dark-800 text-dark-400 border border-dark-600 shrink-0">
              Inactif
            </span>
          )}
        </div>
        {bundle.description && (
          <p className="text-xs text-dark-400 mt-0.5 line-clamp-2">{bundle.description}</p>
        )}
        <div className="flex items-center gap-3 mt-2 flex-wrap">
          <span className="text-sm font-bold whitespace-nowrap">
            {(bundle.bundle_price_euros ?? 0).toFixed(2)} EUR
            <span className="text-xs text-dark-500 font-normal"> / évén.</span>
          </span>
          {bundle.cleaning_fee_cents > 0 && (
            <span className="text-xs text-dark-500">
              + {formatCents(bundle.cleaning_fee_cents)} nettoyage
            </span>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-1 items-start pt-0.5 shrink-0" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={() => onEdit(bundle)}
          className="text-xs px-2 py-1 rounded-lg border border-dark-600 text-dark-400 hover:text-dark-50 hover:bg-dark-600 transition-colors"
        >
          Modifier
        </button>
        <button
          onClick={() => onDelete(bundle)}
          className="text-xs px-2 py-1 rounded-lg border border-dark-600 text-red-400 hover:bg-red-500/10 transition-colors"
        >
          ✕
        </button>
      </div>
    </article>
  )
}

// ── Filters ───────────────────────────────────────────────────────────────

const PACK_FILTERS = [
  { key: 'all', label: 'Tous' },
  { key: 'featured', label: 'Mis en avant' },
  { key: 'mariage', label: 'Mariage' },
  { key: 'cocktail', label: 'Cocktail' },
  { key: 'entreprise', label: 'Entreprise' },
]

// ── Main page ─────────────────────────────────────────────────────────────

export default function BundlesPage() {
  const navigate = useNavigate()
  const modal = useMultiModal<Bundle>()
  const { filter: activeFilter = 'all', inactive: showInactive = false } = useSearch({
    strict: false,
  }) as { filter?: string; inactive?: boolean }

  const isFeaturedFilter = activeFilter === 'featured'

  const { data, isLoading, error, refetch } = useBundlesList({
    limit: 100,
    active_only: !showInactive,
    featured: isFeaturedFilter ? true : undefined,
  })

  const updateBundle = useUpdateBundle()

  // Local drag & drop order
  const [orderedBundles, setOrderedBundles] = useState<Bundle[]>([])
  const dragIndexRef = useRef<number | null>(null)
  const [draggingIdx, setDraggingIdx] = useState<number | null>(null)

  useEffect(() => {
    const items = data?.items ?? []
    setOrderedBundles([...items].sort((a, b) => a.display_order - b.display_order))
  }, [data?.items])

  // Client-side text filter (sauf 'all' et 'featured' déjà gérés côté API)
  const filtered = isFeaturedFilter || activeFilter === 'all'
    ? orderedBundles
    : orderedBundles.filter((b) => {
        const text = `${b.name} ${b.description || ''}`.toLowerCase()
        return text.includes(activeFilter)
      })

  const totalBundles = data?.items?.length ?? 0

  // ── Drag & drop handlers ─────────────────────────────────────────────────

  const handleDragStart = (idx: number) => {
    dragIndexRef.current = idx
    setDraggingIdx(idx)
  }

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault()
    if (dragIndexRef.current === null || dragIndexRef.current === idx) return
    const newOrder = [...orderedBundles]
    const [dragged] = newOrder.splice(dragIndexRef.current, 1)
    newOrder.splice(idx, 0, dragged)
    dragIndexRef.current = idx
    setOrderedBundles(newOrder)
  }

  const handleDrop = () => {
    setDraggingIdx(null)
    dragIndexRef.current = null
    // Persist only changed display_order values
    orderedBundles.forEach((b, i) => {
      const newOrder = i + 1
      if (b.display_order !== newOrder) {
        updateBundle.mutate({ id: b.id, data: { display_order: newOrder } })
      }
    })
  }

  const handleDragEnd = () => {
    setDraggingIdx(null)
    dragIndexRef.current = null
  }

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      <PageHeader title="Packs & Formules" subtitle="Composez des offres groupées pour vos clients" />

      {/* ── Filtres + Toggle inactifs ─────────────────────────────────── */}
      <div className="flex gap-2 flex-wrap items-center">
        {PACK_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() =>
              navigate({
                search: (prev: Record<string, unknown>) => ({
                  ...prev,
                  filter: f.key === 'all' ? undefined : f.key,
                }),
              })
            }
            className={cn(
              'px-4 py-1 text-xs font-medium rounded-full border transition-colors',
              activeFilter === f.key
                ? 'bg-primary-500 border-primary-500 text-white'
                : 'bg-dark-900 border-dark-600 text-dark-400 hover:bg-dark-600',
            )}
          >
            {f.label}
          </button>
        ))}

        {/* Toggle inactifs */}
        <button
          onClick={() =>
            navigate({
              search: (prev: Record<string, unknown>) => ({
                ...prev,
                inactive: showInactive ? undefined : true,
              }),
            })
          }
          className={cn(
            'flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full border transition-colors',
            showInactive
              ? 'bg-dark-700 border-dark-500 text-dark-200'
              : 'bg-dark-900 border-dark-600 text-dark-500 hover:bg-dark-600',
          )}
        >
          {showInactive ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          Inactifs
        </button>

        <button
          onClick={() => modal.open('create')}
          className="ml-auto flex items-center gap-1.5 px-4 py-1 text-xs font-medium rounded-full bg-primary-500 text-white hover:bg-primary-500/90 transition-colors"
        >
          <Plus className="w-3 h-3" />
          Nouveau pack
        </button>
      </div>

      {/* ── Workflow strip ───────────────────────────────────────────── */}
      <div className="space-y-2">
        <WorkflowStep num={1} title="Qualifier le besoin" sub="Filtrer les packs par type d'événement." chip="Filtrer" chipColor="green" />
        <WorkflowStep num={2} title="Comparer les contenus" sub="Consulter documents, tarifs et quantités associées." chip="Comparer" chipColor="orange" onClick={() => navigate({ to: '/catalogue/comparator' })} />
        <WorkflowStep num={3} title="Composer ou personnaliser" sub="Basculer vers le builder pour affiner la proposition." chip="Composer" chipColor="blue" onClick={() => navigate({ to: '/catalogue/bundles' })} />
      </div>

      {/* ── Liste packs ─────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => <PackCardSkeleton key={i} />)}
        </div>
      ) : error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : filtered.length === 0 ? (
        totalBundles === 0 ? (
          <NoData onAction={() => modal.open('create')} actionLabel="Nouveau pack" />
        ) : (
          <div className="text-center py-10 text-dark-400 text-sm">Aucun pack pour ce filtre</div>
        )
      ) : (
        <div className="space-y-3">
          {filtered.map((bundle, idx) => (
            <div
              key={bundle.id}
              draggable
              onDragStart={() => handleDragStart(idx)}
              onDragOver={(e) => handleDragOver(e, idx)}
              onDrop={handleDrop}
              onDragEnd={handleDragEnd}
            >
              <PackCard
                bundle={bundle}
                onEdit={(b) => modal.open('edit', b)}
                onDelete={(b) => modal.open('delete', b)}
                isDragging={draggingIdx === idx}
                dragHandleProps={{}}
              />
            </div>
          ))}
          {updateBundle.isPending && (
            <p className="text-xs text-dark-500 text-center py-1">Enregistrement de l'ordre…</p>
          )}
        </div>
      )}

      {/* ── Boutons action ──────────────────────────────────────────── */}
      <div className="flex gap-4 pt-2">
        <button
          onClick={() => modal.open('create')}
          className="flex-1 py-2.5 rounded-xl bg-primary-500 text-white text-sm font-medium hover:bg-primary-500/90 transition-colors"
        >
          Créer une offre pack
        </button>
        <button
          onClick={() => navigate({ to: '/catalogue/comparator' })}
          className="flex-1 py-2.5 rounded-xl border border-dark-600 text-dark-300 text-sm font-medium hover:bg-dark-600 transition-colors"
        >
          Comparer les packs
        </button>
      </div>

      <p
        className="text-xs text-dark-400 hover:text-primary-400 text-center cursor-pointer transition-colors"
        onClick={() => navigate({ to: '/catalogue/tools' })}
      >
        Accéder aux outils de pilotage →
      </p>

      {/* ── Modals ──────────────────────────────────────────────────── */}
      <BundleFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        bundle={modal.data}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />
      <BundleDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        bundle={modal.data}
      />
    </div>
  )
}

// ── WorkflowStep ──────────────────────────────────────────────────────────

function WorkflowStep({ num, title, sub, chip, chipColor, onClick }: {
  num: number; title: string; sub: string; chip: string; chipColor: string; onClick?: () => void
}) {
  const CHIP_COLORS: Record<string, string> = {
    green:  'bg-green-500/10 text-green-400 border-green-500/20',
    orange: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    blue:   'bg-blue-500/10 text-blue-400 border-blue-500/20',
  }
  return (
    <div
      className={cn('flex items-center gap-4 p-4 card', onClick && 'cursor-pointer hover:shadow-md')}
      onClick={onClick}
    >
      <div className="w-7 h-7 rounded-full bg-dark-800 border border-dark-600 text-xs font-bold flex items-center justify-center shrink-0 text-dark-300">
        {num}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold">{title}</p>
        <p className="text-xs text-dark-400 mt-0.5">{sub}</p>
      </div>
      <span className={cn('text-xs px-2 py-0.5 rounded-full border font-medium shrink-0', CHIP_COLORS[chipColor])}>
        {chip}
      </span>
    </div>
  )
}
