import { useState } from 'react'
import { useParams, Link } from '@tanstack/react-router'
import {
  ArrowLeft,
  Box,
  Boxes,
  Layers,
  Shirt,
  Archive,
  Plus,
  Minus,
  Trash2,
  Package,
  Clock,
  Info,
  Pencil,
  Truck,
  RotateCcw,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  useContainerDetailQuery,
  useContainerHistory,
  useAddContainerContent,
  useUpdateContainerContent,
  useRemoveContainerContent,
} from '@/api/queries/useContainers'
import type { ContainerType, ContainerContent, ContainerDetail } from '@/types/container'
import { CONTAINER_TYPE_LABELS } from '@/types/container'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { normalizeError } from '@shared/errors/normalizer'
import AddContentSheet from './components/AddContentSheet'

// ── Constants ───────────────────────────────────────────────────────────────

const TYPE_ICONS: Record<ContainerType, typeof Box> = {
  bac: Box,
  carton: Boxes,
  palette: Layers,
  housse: Shirt,
  caisse: Archive,
}

const TYPE_COLORS: Record<ContainerType, string> = {
  bac: 'bg-blue-500/10 text-blue-400',
  carton: 'bg-orange-500/10 text-orange-400',
  palette: 'bg-purple-500/10 text-purple-400',
  housse: 'bg-pink-500/10 text-pink-400',
  caisse: 'bg-green-500/10 text-green-400',
}

type Tab = 'contenu' | 'infos' | 'historique'

// ── Skeleton ────────────────────────────────────────────────────────────────

function DetailSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-[var(--s2)] rounded" />
        <div className="h-6 bg-[var(--s2)] rounded w-48" />
      </div>
      <div className="card p-4 space-y-3">
        <div className="flex gap-3">
          <div className="w-12 h-12 bg-[var(--s2)] rounded-xl" />
          <div className="space-y-2 flex-1">
            <div className="h-5 bg-[var(--s2)] rounded w-40" />
            <div className="h-4 bg-[var(--s2)] rounded w-24" />
          </div>
        </div>
      </div>
      <div className="flex gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-9 bg-[var(--s2)] rounded-full w-24" />
        ))}
      </div>
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="card p-4 space-y-2">
          <div className="h-4 bg-[var(--s2)] rounded w-3/4" />
          <div className="h-3 bg-[var(--s2)] rounded w-1/3" />
        </div>
      ))}
    </div>
  )
}

// ── Content Row ─────────────────────────────────────────────────────────────

function ContentRow({
  item,
  containerId,
}: {
  item: ContainerContent
  containerId: number
}) {
  const updateMut = useUpdateContainerContent()
  const removeMut = useRemoveContainerContent()
  const [editing, setEditing] = useState(false)
  const [qty, setQty] = useState(String(item.quantity))

  const handleSave = () => {
    const n = Number(qty)
    if (n > 0 && n !== item.quantity) {
      updateMut.mutate(
        { containerId, contentId: item.id, data: { quantity: n } },
        { onSuccess: () => setEditing(false) }
      )
    } else {
      setEditing(false)
    }
  }

  return (
    <div className="card-inner p-3 flex items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-[var(--pink)]/10 flex items-center justify-center shrink-0">
        <Package size={16} className="text-[var(--pink)]" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[var(--text)] truncate">
          {item.product_name || `Produit #${item.product_id}`}
        </p>
        {item.variant_label && (
          <p className="text-xs text-[var(--muted)]">{item.variant_label}</p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {editing ? (
          <div className="flex items-center gap-1">
            <input
              className="input w-16 text-center text-sm py-1"
              type="number"
              min="1"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSave()}
              autoFocus
            />
            <button onClick={handleSave} className="text-xs text-[var(--green)] font-medium px-2 py-1">
              OK
            </button>
          </div>
        ) : (
          <button
            onClick={() => { setQty(String(item.quantity)); setEditing(true) }}
            className="text-sm font-semibold text-[var(--text)] bg-[var(--s2)] px-3 py-1 rounded-lg hover:bg-[var(--border)] transition-colors"
          >
            x{item.quantity}
          </button>
        )}
        <button
          onClick={() => removeMut.mutate({ containerId, contentId: item.id })}
          disabled={removeMut.isPending}
          className="p-1.5 rounded-lg hover:bg-[var(--red)]/10 text-[var(--muted)] hover:text-[var(--red)] transition-colors"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  )
}

// ── Tab: Contenu ────────────────────────────────────────────────────────────

function ContenuTab({ container }: { container: ContainerDetail }) {
  const [addOpen, setAddOpen] = useState(false)

  return (
    <div className="space-y-3">
      {/* Summary bar */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--muted)]">
          {container.contents_count} produit{container.contents_count > 1 ? 's' : ''} · {container.total_items} unite{container.total_items > 1 ? 's' : ''}
        </p>
        <button
          onClick={() => setAddOpen(true)}
          className="btn btn-primary text-sm flex items-center gap-1.5"
        >
          <Plus size={14} /> Ajouter
        </button>
      </div>

      {/* Content list */}
      {container.contents.length === 0 ? (
        <div className="card p-8 text-center">
          <Package size={36} className="mx-auto mb-3 text-[var(--muted2)]" />
          <p className="text-sm text-[var(--muted)]">Ce contenant est vide</p>
          <button
            onClick={() => setAddOpen(true)}
            className="mt-3 text-sm text-[var(--pink)] font-medium"
          >
            Ajouter des produits
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {container.contents.map((cc) => (
            <ContentRow key={cc.id} item={cc} containerId={container.id} />
          ))}
        </div>
      )}

      <AddContentSheet
        isOpen={addOpen}
        onClose={() => setAddOpen(false)}
        containerId={container.id}
      />
    </div>
  )
}

// ── Tab: Infos ──────────────────────────────────────────────────────────────

function InfosTab({ container }: { container: ContainerDetail }) {
  const Icon = TYPE_ICONS[container.container_type]

  const rows: { label: string; value: string | null }[] = [
    { label: 'Type', value: CONTAINER_TYPE_LABELS[container.container_type] },
    { label: 'N. serie', value: container.serial_number || null },
    {
      label: 'Dimensions',
      value:
        container.length_cm && container.width_cm && container.height_cm
          ? `${container.length_cm} x ${container.width_cm} x ${container.height_cm} cm`
          : null,
    },
    {
      label: 'Poids max',
      value: container.max_weight_grams
        ? `${(container.max_weight_grams / 1000).toFixed(1)} kg`
        : null,
    },
    {
      label: 'Disponibilite',
      value: container.is_available ? 'Disponible' : 'Affecte a un mouvement',
    },
    { label: 'Notes', value: container.notes || null },
  ]

  return (
    <div className="space-y-3">
      <div className="card p-4">
        <div className="space-y-3">
          {rows.map((r) =>
            r.value ? (
              <div key={r.label} className="flex items-start justify-between gap-4">
                <span className="text-sm text-[var(--muted)] shrink-0">{r.label}</span>
                <span className="text-sm text-[var(--text)] text-right">{r.value}</span>
              </div>
            ) : null
          )}
        </div>
      </div>
      <p className="text-xs text-[var(--muted2)]">
        Cree le {new Date(container.created_at).toLocaleDateString('fr-FR')} · Modifie le {new Date(container.updated_at).toLocaleDateString('fr-FR')}
      </p>
    </div>
  )
}

// ── Tab: Historique ─────────────────────────────────────────────────────────

function HistoriqueTab({ containerId }: { containerId: number }) {
  const { data: history, isLoading } = useContainerHistory(containerId)

  if (isLoading) {
    return (
      <div className="space-y-3 animate-pulse">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card p-4 space-y-2">
            <div className="h-4 bg-[var(--s2)] rounded w-1/2" />
            <div className="h-3 bg-[var(--s2)] rounded w-1/3" />
          </div>
        ))}
      </div>
    )
  }

  if (!history || history.length === 0) {
    return (
      <div className="card p-8 text-center">
        <Clock size={36} className="mx-auto mb-3 text-[var(--muted2)]" />
        <p className="text-sm text-[var(--muted)]">Aucun mouvement enregistre</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {history.map((entry, i) => {
        const isDeparture = entry.movement_type === 'departure'
        return (
          <div key={i} className="card-inner p-3 flex items-center gap-3">
            <div className={cn(
              'w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
              isDeparture ? 'bg-[var(--orange)]/10' : 'bg-[var(--blue)]/10'
            )}>
              {isDeparture ? <Truck size={16} className="text-[var(--orange)]" /> : <RotateCcw size={16} className="text-[var(--blue)]" />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[var(--text)]">
                {isDeparture ? 'Depart' : 'Retour'} #{entry.movement_id}
              </p>
              {entry.reservation_reference && (
                <p className="text-xs text-[var(--muted)]">Reservation {entry.reservation_reference}</p>
              )}
              <p className="text-xs text-[var(--muted2)]">
                {entry.items_summary.length} article{entry.items_summary.length > 1 ? 's' : ''}
              </p>
            </div>
            <span className={cn(
              'text-xs px-2 py-0.5 rounded-full font-medium',
              entry.status === 'completed' ? 'bg-[var(--green)]/10 text-[var(--green)]' : 'bg-[var(--muted)]/10 text-[var(--muted)]'
            )}>
              {entry.status}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function ContainerDetailPage() {
  const { id } = useParams({ from: '/_app/stock/containers/$id' })
  const containerId = Number(id)
  const { data: container, isLoading, isError, refetch } = useContainerDetailQuery(containerId)
  const [activeTab, setActiveTab] = useState<Tab>('contenu')

  if (isLoading) return <DetailSkeleton />
  if (isError || !container) return <ErrorState onRetry={() => refetch()} />

  const Icon = TYPE_ICONS[container.container_type]

  const tabs: { key: Tab; label: string; icon: typeof Package }[] = [
    { key: 'contenu', label: 'Contenu', icon: Package },
    { key: 'infos', label: 'Infos', icon: Info },
    { key: 'historique', label: 'Historique', icon: Clock },
  ]

  return (
    <div className="space-y-4">
      {/* Back + Header */}
      <div className="flex items-center gap-3">
        <Link to="/stock/containers" className="p-1.5 rounded-lg hover:bg-[var(--s2)] transition-colors">
          <ArrowLeft size={20} className="text-[var(--muted)]" />
        </Link>
        <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center', TYPE_COLORS[container.container_type])}>
          <Icon size={20} />
        </div>
        <div>
          <h1 className="text-lg font-display font-bold text-[var(--text)]">{container.name}</h1>
          <p className="text-xs text-[var(--muted)]">
            {CONTAINER_TYPE_LABELS[container.container_type]}
            {container.serial_number && ` · ${container.serial_number}`}
          </p>
        </div>
        <div className="ml-auto">
          <span className={cn(
            'text-xs px-2.5 py-0.5 rounded-full font-medium',
            container.is_available
              ? 'bg-[var(--green)]/10 text-[var(--green)]'
              : 'bg-[var(--orange)]/10 text-[var(--orange)]'
          )}>
            {container.is_available ? 'Disponible' : 'Affecte'}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-[var(--s2)] rounded-xl p-1">
        {tabs.map((t) => {
          const TabIcon = t.icon
          return (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={cn(
                'flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                activeTab === t.key
                  ? 'bg-[var(--s1)] text-[var(--text)] shadow-sm'
                  : 'text-[var(--muted)] hover:text-[var(--text)]'
              )}
            >
              <TabIcon size={14} />
              {t.label}
              {t.key === 'contenu' && container.contents_count > 0 && (
                <span className="text-xs bg-[var(--pink)]/10 text-[var(--pink)] px-1.5 py-0.5 rounded-full">
                  {container.contents_count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      {activeTab === 'contenu' && <ContenuTab container={container} />}
      {activeTab === 'infos' && <InfosTab container={container} />}
      {activeTab === 'historique' && <HistoriqueTab containerId={containerId} />}
    </div>
  )
}
