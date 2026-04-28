import { useState } from 'react'
import { useParams } from '@tanstack/react-router'
import { Wrench, Plus, Trash2, CheckCircle, Clock, XCircle } from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import { useProductDetail } from '@/api/queries/useProducts'
import {
  useProductMaintenances,
  useCreateMaintenance,
  useUpdateMaintenance,
  useDeleteMaintenance,
} from '@/api/queries/useProducts'
import type { Maintenance, MaintenanceStatus } from '@/types/maintenance'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { ActionError } from '@shared/components/ui'
import { MoneyInput } from '@shared/components/ui/MoneyInput'
import { normalizeError } from '@shared/errors/normalizer'
import { formatCents } from '@/lib/utils'

const STATUS_LABELS: Record<MaintenanceStatus, string> = {
  scheduled: 'Planifiée',
  in_progress: 'En cours',
  completed: 'Terminée',
  cancelled: 'Annulée',
}

const STATUS_COLORS: Record<MaintenanceStatus, string> = {
  scheduled: 'bg-yellow-900/40 text-yellow-300 border-yellow-700/40',
  in_progress: 'bg-blue-900/40 text-blue-300 border-blue-700/40',
  completed: 'bg-green-900/40 text-green-300 border-green-700/40',
  cancelled: 'bg-dark-900 text-dark-400 border-dark-600',
}

const NEXT_STATUS: Partial<Record<MaintenanceStatus, MaintenanceStatus>> = {
  scheduled: 'in_progress',
  in_progress: 'completed',
}

function formatDate(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('fr-FR')
}

interface AddFormProps {
  productId: number
  onClose: () => void
}

function AddMaintenanceForm({ productId, onClose }: AddFormProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [scheduledDate, setScheduledDate] = useState('')
  const [costCents, setCostCents] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const createMutation = useCreateMaintenance(productId)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    createMutation.mutate(
      {
        title: title.trim(),
        description: description.trim() || undefined,
        scheduled_date: scheduledDate || undefined,
        cost_cents: costCents > 0 ? costCents : undefined,
      },
      {
        onSuccess: onClose,
        onError: (err) => setError(normalizeError(err).message || 'Erreur lors de la création'),
      },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="card p-4 space-y-4">
      <h3 className="font-medium">Nouvelle maintenance</h3>
      <div>
        <label className="block text-dark-300 text-xs mb-1">Titre *</label>
        <input
          className="input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Ex : Révision annuelle"
          required
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-dark-300 text-xs mb-1">Date planifiée</label>
          <input
            type="date"
            className="input"
            value={scheduledDate}
            onChange={(e) => setScheduledDate(e.target.value)}
          />
        </div>
        <MoneyInput
          label="Coût estimé"
          value={costCents}
          onChange={setCostCents}
          min={0}
        />
      </div>
      <div>
        <label className="block text-dark-300 text-xs mb-1">Description</label>
        <textarea
          className="input w-full resize-none"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Détails optionnels…"
        />
      </div>
      {error && <ActionError message={error} onDismiss={() => setError(null)} />}
      <div className="flex gap-2 justify-end">
        <button type="button" className="btn-secondary text-sm px-4 py-1.5" onClick={onClose}>
          Annuler
        </button>
        <button
          type="submit"
          disabled={createMutation.isPending}
          className="btn-primary text-sm px-4 py-1.5"
        >
          {createMutation.isPending ? 'Création…' : 'Créer'}
        </button>
      </div>
    </form>
  )
}

interface MaintenanceRowProps {
  item: Maintenance
  productId: number
}

function MaintenanceRow({ item, productId }: MaintenanceRowProps) {
  const updateMutation = useUpdateMaintenance(productId)
  const deleteMutation = useDeleteMaintenance(productId)
  const [rowError, setRowError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const nextStatus = NEXT_STATUS[item.status as MaintenanceStatus]

  function handleDelete() {
    if (!confirmDelete) { setConfirmDelete(true); return }
    deleteMutation.mutate(item.id, {
      onError: (err) => setRowError(normalizeError(err).message || 'Erreur lors de la suppression'),
    })
    setConfirmDelete(false)
  }

  function handleAdvance() {
    if (!nextStatus) return
    updateMutation.mutate(
      {
        id: item.id,
        data: {
          status: nextStatus,
          ...(nextStatus === 'completed'
            ? { completed_date: new Date().toISOString().split('T')[0] }
            : {}),
        },
      },
      { onError: (err) => setRowError(normalizeError(err).message || 'Erreur mise à jour') },
    )
  }

  function handleCancel() {
    updateMutation.mutate(
      { id: item.id, data: { status: 'cancelled' } },
      { onError: (err) => setRowError(normalizeError(err).message || 'Erreur annulation') },
    )
  }

  return (
    <div className="hover:bg-dark-600/30 transition-colors">
      <div className="px-4 py-4 flex items-start gap-4">
        <div className="shrink-0 pt-0.5">
          <span
            className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
              STATUS_COLORS[item.status as MaintenanceStatus] ?? 'bg-dark-900 text-dark-400 border-dark-600'
            }`}
          >
            {STATUS_LABELS[item.status as MaintenanceStatus] ?? item.status}
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium">{item.title}</p>
          {item.description && (
            <p className="text-dark-400 text-xs mt-0.5 line-clamp-2">{item.description}</p>
          )}
          <div className="flex gap-4 mt-1">
            {item.scheduled_date && (
              <span className="flex items-center gap-1 text-dark-400 text-xs">
                <Clock className="w-3 h-3" />
                Planifiée : {formatDate(item.scheduled_date)}
              </span>
            )}
            {item.completed_date && (
              <span className="flex items-center gap-1 text-green-400 text-xs">
                <CheckCircle className="w-3 h-3" />
                Terminée : {formatDate(item.completed_date)}
              </span>
            )}
            {item.cost_cents !== null && (
              <span className="text-dark-400 text-xs">Coût : {formatCents(item.cost_cents)}</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {nextStatus && (
            <button
              onClick={handleAdvance}
              disabled={updateMutation.isPending}
              className="text-xs px-2 py-1 rounded bg-dark-900 hover:bg-dark-600 text-dark-200 transition-colors"
            >
              → {STATUS_LABELS[nextStatus]}
            </button>
          )}
          {item.status !== 'cancelled' && item.status !== 'completed' && (
            <button
              onClick={handleCancel}
              disabled={updateMutation.isPending}
              className="text-dark-500 hover:text-orange-400 transition-colors p-1"
              title="Annuler"
            >
              <XCircle className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className={`transition-colors p-1 text-xs flex items-center gap-1 ${
              confirmDelete
                ? 'text-red-400 font-medium'
                : 'text-dark-500 hover:text-red-400'
            }`}
            title={confirmDelete ? 'Cliquer pour confirmer' : 'Supprimer'}
            onBlur={() => setConfirmDelete(false)}
          >
            <Trash2 className="w-4 h-4" />
            {confirmDelete && <span>Confirmer ?</span>}
          </button>
        </div>
      </div>
      {rowError && (
        <div className="px-4 pb-3">
          <ActionError message={rowError} onDismiss={() => setRowError(null)} />
        </div>
      )}
    </div>
  )
}

export default function MaintenancePage() {
  const { id: rawId } = useParams({ strict: false }) as { id: string }
  const id = parseInt(rawId, 10)
  const [showAddForm, setShowAddForm] = useState(false)

  const { data: product } = useProductDetail(isNaN(id) ? null : id)
  const { data: maintenances, isLoading, error, refetch } = useProductMaintenances(isNaN(id) ? null : id)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-4">
          <BackButton />
          <Wrench className="w-5 h-5 text-gold-400" />
          <h1 className="text-xl font-semibold">
            Maintenances — {product?.name ?? (isNaN(id) ? 'Produit' : `Produit #${rawId}`)}
          </h1>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="btn-primary flex items-center gap-2 text-sm px-4 py-1.5"
        >
          <Plus className="w-4 h-4" />
          Ajouter
        </button>
      </div>

      {showAddForm && !isNaN(id) && (
        <AddMaintenanceForm productId={id} onClose={() => setShowAddForm(false)} />
      )}

      {isLoading ? (
        <div className="card divide-y divide-dark-600 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-start gap-4 p-4">
              <div className="w-8 h-8 skel rounded-lg shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-40" />
                <div className="h-2 skel rounded w-64" />
              </div>
              <div className="h-5 skel rounded w-20 shrink-0" />
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : !maintenances || maintenances.length === 0 ? (
        <div className="card text-center py-14">
          <Wrench className="w-10 h-10 text-dark-500 mx-auto mb-4" />
          <p className="font-medium">Aucune maintenance</p>
          <p className="text-dark-400 text-sm mt-1">
            Ce produit n'a pas encore de maintenance planifiée.
          </p>
        </div>
      ) : (
        <div className="card divide-y divide-dark-600">
          {maintenances.map((m) => (
            <MaintenanceRow key={m.id} item={m} productId={id} />
          ))}
        </div>
      )}
    </div>
  )
}
