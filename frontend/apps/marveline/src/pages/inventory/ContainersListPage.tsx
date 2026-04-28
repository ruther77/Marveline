import { useState, useMemo } from 'react'
import { Link } from '@tanstack/react-router'
import {
  Plus,
  Search,
  Package,
  Box,
  Layers,
  Shirt,
  Archive,
  Boxes,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useContainersList, useCreateContainer, useUpdateContainer, useDeleteContainer } from '@/api/queries/useContainers'
import type { Container, ContainerCreate, ContainerUpdate, ContainerType } from '@/types/container'
import { CONTAINER_TYPE_LABELS } from '@/types/container'
import { BottomSheet } from '@shared/components/ui/BottomSheet'
import { ModalFooter } from '@shared/components/ui/Modal'
import { ErrorState, NoData, NoSearchResults } from '@shared/components/ui/EmptyState'
import { normalizeError } from '@shared/errors/normalizer'
import { useDebounce } from '@/hooks/useDebounce'

// ── Constants ───────────────────────────────────────────────────────────────

const TYPE_OPTIONS: { value: ContainerType; label: string }[] = [
  { value: 'bac', label: 'Bac' },
  { value: 'carton', label: 'Carton' },
  { value: 'palette', label: 'Palette' },
  { value: 'housse', label: 'Housse' },
  { value: 'caisse', label: 'Caisse' },
]

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

type TypeFilter = ContainerType | 'all'

// ── Skeleton ────────────────────────────────────────────────────────────────

function ContainerCardSkeleton() {
  return (
    <div className="card p-4 animate-pulse space-y-3">
      <div className="flex gap-3">
        <div className="w-10 h-10 bg-[var(--s2)] rounded-xl shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-[var(--s2)] rounded w-3/4" />
          <div className="h-3 bg-[var(--s2)] rounded w-1/3" />
        </div>
      </div>
      <div className="flex gap-2">
        <div className="h-5 bg-[var(--s2)] rounded-full w-16" />
        <div className="h-5 bg-[var(--s2)] rounded-full w-20" />
      </div>
    </div>
  )
}

// ── Form Modal ──────────────────────────────────────────────────────────────

function ContainerFormModal({
  isOpen,
  onClose,
  container,
}: {
  isOpen: boolean
  onClose: () => void
  container?: Container | null
}) {
  const isEdit = !!container
  const [name, setName] = useState('')
  const [containerType, setContainerType] = useState<ContainerType>('bac')
  const [serialNumber, setSerialNumber] = useState('')
  const [lengthCm, setLengthCm] = useState('')
  const [widthCm, setWidthCm] = useState('')
  const [heightCm, setHeightCm] = useState('')
  const [maxWeightGrams, setMaxWeightGrams] = useState('')
  const [notes, setNotes] = useState('')

  const createMut = useCreateContainer()
  const updateMut = useUpdateContainer()
  const error = createMut.error || updateMut.error

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useState(() => {
    if (isOpen && container) {
      setName(container.name)
      setContainerType(container.container_type)
      setSerialNumber(container.serial_number || '')
      setLengthCm(container.length_cm?.toString() || '')
      setWidthCm(container.width_cm?.toString() || '')
      setHeightCm(container.height_cm?.toString() || '')
      setMaxWeightGrams(container.max_weight_grams?.toString() || '')
      setNotes(container.notes || '')
    } else if (isOpen) {
      setName('')
      setContainerType('bac')
      setSerialNumber('')
      setLengthCm('')
      setWidthCm('')
      setHeightCm('')
      setMaxWeightGrams('')
      setNotes('')
    }
  })

  const handleSubmit = () => {
    const data: ContainerCreate | ContainerUpdate = {
      name,
      container_type: containerType,
      serial_number: serialNumber || null,
      length_cm: lengthCm ? Number(lengthCm) : null,
      width_cm: widthCm ? Number(widthCm) : null,
      height_cm: heightCm ? Number(heightCm) : null,
      max_weight_grams: maxWeightGrams ? Number(maxWeightGrams) : null,
      notes: notes || null,
    }
    if (isEdit && container) {
      updateMut.mutate({ id: container.id, data }, { onSuccess: onClose })
    } else {
      createMut.mutate(data as ContainerCreate, { onSuccess: onClose })
    }
  }

  return (
    <BottomSheet
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier le contenant' : 'Nouveau contenant'}
      size="lg"
      footer={
        <ModalFooter
          onCancel={onClose}
          onConfirm={handleSubmit}
          confirmText={isEdit ? 'Enregistrer' : 'Creer'}
          loading={createMut.isPending || updateMut.isPending}
        />
      }
    >
      <div className="space-y-4">
        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-[var(--red)] text-sm">
            {normalizeError(error).message || 'Une erreur est survenue'}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-[var(--muted)] mb-1">Nom *</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Palette A3" />
          </div>
          <div>
            <label className="block text-sm text-[var(--muted)] mb-1">Type *</label>
            <select className="input" value={containerType} onChange={(e) => setContainerType(e.target.value as ContainerType)}>
              {TYPE_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">N. serie</label>
          <input className="input" value={serialNumber} onChange={(e) => setSerialNumber(e.target.value)} placeholder="PAL-A3-001" />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-sm text-[var(--muted)] mb-1">L (cm)</label>
            <input className="input" type="number" min="0" value={lengthCm} onChange={(e) => setLengthCm(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm text-[var(--muted)] mb-1">l (cm)</label>
            <input className="input" type="number" min="0" value={widthCm} onChange={(e) => setWidthCm(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm text-[var(--muted)] mb-1">H (cm)</label>
            <input className="input" type="number" min="0" value={heightCm} onChange={(e) => setHeightCm(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">Poids max (g)</label>
          <input className="input" type="number" min="0" value={maxWeightGrams} onChange={(e) => setMaxWeightGrams(e.target.value)} placeholder="25000" />
        </div>
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">Notes</label>
          <textarea className="input min-h-[60px]" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>
    </BottomSheet>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ContainersListPage() {
  const { data, isLoading, isError, refetch } = useContainersList()
  const deleteMut = useDeleteContainer()
  const [formOpen, setFormOpen] = useState(false)
  const [editItem, setEditItem] = useState<Container | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Container | null>(null)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')
  const debouncedSearch = useDebounce(search, 250)

  const containers = useMemo(() => {
    let items = data?.items ?? []
    if (typeFilter !== 'all') {
      items = items.filter((c) => c.container_type === typeFilter)
    }
    if (debouncedSearch) {
      const q = debouncedSearch.toLowerCase()
      items = items.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          (c.serial_number && c.serial_number.toLowerCase().includes(q))
      )
    }
    return items
  }, [data, typeFilter, debouncedSearch])

  // ── Loading ───────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="h-7 bg-[var(--s2)] rounded w-40 animate-pulse" />
          <div className="h-9 bg-[var(--s2)] rounded-xl w-28 animate-pulse" />
        </div>
        <div className="h-10 bg-[var(--s2)] rounded-xl animate-pulse" />
        <div className="flex gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-8 bg-[var(--s2)] rounded-full w-20 animate-pulse" />
          ))}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <ContainerCardSkeleton key={i} />
          ))}
        </div>
      </div>
    )
  }

  // ── Error ─────────────────────────────────────────────────
  if (isError) {
    return <ErrorState onRetry={() => refetch()} />
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-lg font-display font-bold text-[var(--text)]">Contenants</h1>
        <button
          onClick={() => { setEditItem(null); setFormOpen(true) }}
          className="btn btn-primary flex items-center gap-1.5 text-sm"
        >
          <Plus size={16} /> Ajouter
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
        <input
          className="input pl-9 w-full"
          placeholder="Rechercher par nom ou n. serie..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Type filter pills */}
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
        <button
          onClick={() => setTypeFilter('all')}
          className={cn(
            'px-3 py-1.5 rounded-full text-sm whitespace-nowrap transition-colors',
            typeFilter === 'all'
              ? 'bg-[var(--pink)] text-white'
              : 'bg-[var(--s1)] text-[var(--muted)] hover:text-[var(--text)]'
          )}
        >
          Tous ({data?.items?.length ?? 0})
        </button>
        {TYPE_OPTIONS.map((t) => {
          const count = (data?.items ?? []).filter((c) => c.container_type === t.value).length
          const Icon = TYPE_ICONS[t.value]
          return (
            <button
              key={t.value}
              onClick={() => setTypeFilter(t.value)}
              className={cn(
                'px-3 py-1.5 rounded-full text-sm whitespace-nowrap flex items-center gap-1.5 transition-colors',
                typeFilter === t.value
                  ? 'bg-[var(--pink)] text-white'
                  : 'bg-[var(--s1)] text-[var(--muted)] hover:text-[var(--text)]'
              )}
            >
              <Icon size={14} />
              {t.label} ({count})
            </button>
          )
        })}
      </div>

      {/* Content */}
      {containers.length === 0 ? (
        debouncedSearch ? (
          <NoSearchResults searchTerm={debouncedSearch} onClear={() => setSearch('')} />
        ) : (
          <NoData
            onAction={() => { setEditItem(null); setFormOpen(true) }}
            actionLabel="Ajouter un contenant"
          />
        )
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {containers.map((c) => {
            const Icon = TYPE_ICONS[c.container_type]
            return (
              <Link
                key={c.id}
                to="/stock/containers/$id"
                params={{ id: String(c.id) }}
                className="card p-4 hover:shadow-md transition-shadow group"
              >
                <div className="flex items-start gap-3">
                  <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center shrink-0', TYPE_COLORS[c.container_type])}>
                    <Icon size={20} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <p className="font-medium text-[var(--text)] text-sm truncate">{c.name}</p>
                      <ChevronRight size={16} className="text-[var(--muted)] opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                    </div>
                    <p className="text-xs text-[var(--muted)] mt-0.5">
                      {CONTAINER_TYPE_LABELS[c.container_type]}
                      {c.serial_number && <span className="text-[var(--muted2)]"> · {c.serial_number}</span>}
                    </p>
                    {(c.length_cm || c.max_weight_grams) && (
                      <p className="text-xs text-[var(--muted2)] mt-1">
                        {c.length_cm && c.width_cm && c.height_cm && `${c.length_cm} x ${c.width_cm} x ${c.height_cm} cm`}
                        {c.length_cm && c.max_weight_grams && ' · '}
                        {c.max_weight_grams && `max ${(c.max_weight_grams / 1000).toFixed(1)} kg`}
                      </p>
                    )}
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <span className={cn(
                    'text-xs px-2.5 py-0.5 rounded-full font-medium',
                    c.is_available
                      ? 'bg-[var(--green)]/10 text-[var(--green)]'
                      : 'bg-[var(--orange)]/10 text-[var(--orange)]'
                  )}>
                    {c.is_available ? 'Disponible' : 'Affecte'}
                  </span>
                </div>
              </Link>
            )
          })}
        </div>
      )}

      {/* Form modal */}
      <ContainerFormModal
        isOpen={formOpen}
        onClose={() => { setFormOpen(false); setEditItem(null) }}
        container={editItem}
      />

      {/* Delete confirmation */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="modal-panel w-full max-w-md p-6 space-y-4">
            <h2 className="text-lg font-bold text-[var(--red)]">Supprimer le contenant</h2>
            <p className="text-sm text-[var(--muted)]">
              Supprimer <strong>{deleteTarget.name}</strong> ? Cette action est irreversible.
            </p>
            <div className="flex gap-4">
              <button onClick={() => setDeleteTarget(null)} className="btn-secondary flex-1">Annuler</button>
              <button
                onClick={() => deleteMut.mutate(deleteTarget.id, { onSuccess: () => setDeleteTarget(null) })}
                disabled={deleteMut.isPending}
                className="flex-1 py-2 rounded-xl bg-[var(--red)] hover:brightness-110 text-white font-medium transition-all"
              >
                Supprimer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
