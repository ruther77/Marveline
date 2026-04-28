import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { Plus, Package, Pencil, Trash2 } from 'lucide-react'
import { useContainersList, useCreateContainer, useUpdateContainer, useDeleteContainer } from '@/api/queries/useContainers'
import type { Container, ContainerCreate, ContainerUpdate, ContainerType } from '@/types/container'
import { CONTAINER_TYPE_LABELS } from '@/types/container'
import { BottomSheet } from '@shared/components/ui/BottomSheet'
import { ModalFooter } from '@shared/components/ui/Modal'
import { normalizeError } from '@shared/errors/normalizer'

const TYPE_OPTIONS: { value: ContainerType; label: string }[] = [
  { value: 'bac', label: 'Bac' },
  { value: 'carton', label: 'Carton' },
  { value: 'palette', label: 'Palette' },
  { value: 'housse', label: 'Housse' },
  { value: 'caisse', label: 'Caisse' },
]

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
  const [lengthCm, setLengthCm] = useState<string>('')
  const [widthCm, setWidthCm] = useState<string>('')
  const [heightCm, setHeightCm] = useState<string>('')
  const [maxWeightGrams, setMaxWeightGrams] = useState<string>('')
  const [notes, setNotes] = useState('')

  const createMut = useCreateContainer()
  const updateMut = useUpdateContainer()
  const error = createMut.error || updateMut.error

  // Reset on open
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
          confirmText={isEdit ? 'Enregistrer' : 'Créer'}
          loading={createMut.isPending || updateMut.isPending}
        />
      }
    >
      <div className="space-y-4">
        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {normalizeError(error).message || 'Une erreur est survenue'}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-dark-400 mb-1">Nom *</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Bac plastique 60L" />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">Type *</label>
            <select className="input" value={containerType} onChange={(e) => setContainerType(e.target.value as ContainerType)}>
              {TYPE_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className="block text-sm text-dark-400 mb-1">N° série</label>
          <input className="input" value={serialNumber} onChange={(e) => setSerialNumber(e.target.value)} placeholder="BAC-001" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-sm text-dark-400 mb-1">L (cm)</label>
            <input className="input" type="number" min="0" value={lengthCm} onChange={(e) => setLengthCm(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">l (cm)</label>
            <input className="input" type="number" min="0" value={widthCm} onChange={(e) => setWidthCm(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm text-dark-400 mb-1">H (cm)</label>
            <input className="input" type="number" min="0" value={heightCm} onChange={(e) => setHeightCm(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="block text-sm text-dark-400 mb-1">Poids max (g)</label>
          <input className="input" type="number" min="0" value={maxWeightGrams} onChange={(e) => setMaxWeightGrams(e.target.value)} placeholder="25000" />
        </div>
        <div>
          <label className="block text-sm text-dark-400 mb-1">Notes</label>
          <textarea className="input min-h-[60px]" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>
    </BottomSheet>
  )
}

export default function ContainersPage() {
  const { data, isLoading } = useContainersList()
  const deleteMut = useDeleteContainer()
  const [formOpen, setFormOpen] = useState(false)
  const [editItem, setEditItem] = useState<Container | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Container | null>(null)

  const containers = data?.items ?? []

  if (isLoading) {
    return (
      <div className="space-y-3 animate-pulse">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card p-4 space-y-2">
            <div className="h-4 bg-dark-700 rounded w-48" />
            <div className="h-3 bg-dark-700 rounded w-32" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Contenants" />
        <button
          onClick={() => { setEditItem(null); setFormOpen(true) }}
          className="btn btn-primary flex items-center gap-1.5 text-sm"
        >
          <Plus size={16} /> Ajouter
        </button>
      </div>

      {containers.length === 0 ? (
        <div className="card p-8 text-center text-dark-400">
          <Package size={40} className="mx-auto mb-3 text-dark-600" />
          <p>Aucun contenant. Créez vos bacs, cartons et palettes.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {containers.map((c) => (
            <div key={c.id} className="card p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-white text-sm">{c.name}</p>
                  <p className="text-xs text-dark-400 mt-0.5">
                    {CONTAINER_TYPE_LABELS[c.container_type]} {c.serial_number && `· ${c.serial_number}`}
                  </p>
                  {(c.length_cm || c.max_weight_grams) && (
                    <p className="text-xs text-dark-500 mt-1">
                      {c.length_cm && c.width_cm && c.height_cm && `${c.length_cm}×${c.width_cm}×${c.height_cm} cm`}
                      {c.max_weight_grams && ` · max ${(c.max_weight_grams / 1000).toFixed(1)} kg`}
                    </p>
                  )}
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => { setEditItem(c); setFormOpen(true) }}
                    className="p-1.5 rounded hover:bg-dark-600 text-dark-400 hover:text-white transition-colors"
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    onClick={() => setDeleteTarget(c)}
                    className="p-1.5 rounded hover:bg-dark-600 text-dark-400 hover:text-red-400 transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              <div className="mt-2">
                <span className={`text-xs px-2 py-0.5 rounded-full ${c.is_available ? 'bg-green-500/10 text-green-400' : 'bg-orange-500/10 text-orange-400'}`}>
                  {c.is_available ? 'Disponible' : 'Affecté'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      <ContainerFormModal
        isOpen={formOpen}
        onClose={() => { setFormOpen(false); setEditItem(null) }}
        container={editItem}
      />

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="modal-panel w-full max-w-md p-6 space-y-4">
            <h2 className="text-lg font-bold text-red-400">Supprimer le contenant</h2>
            <p className="text-sm text-dark-300">
              Supprimer <strong>«&nbsp;{deleteTarget.name}&nbsp;»</strong> ? Cette action est irréversible.
            </p>
            <div className="flex gap-4">
              <button onClick={() => setDeleteTarget(null)} className="btn-secondary flex-1">Annuler</button>
              <button
                onClick={() => deleteMut.mutate(deleteTarget.id, { onSuccess: () => setDeleteTarget(null) })}
                disabled={deleteMut.isPending}
                className="flex-1 py-2 rounded-xl bg-red-500 hover:bg-red-600 text-white font-medium transition-colors"
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
