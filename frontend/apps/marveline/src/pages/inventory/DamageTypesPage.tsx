import { useState } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import {
  useDamageTypesList,
  useCreateDamageType,
  useUpdateDamageType,
  useDeleteDamageType,
} from '@/api/queries/useDamageTypes'
import { formatCents } from '@/lib/utils'
import { Plus, Pencil, Trash2, AlertTriangle, ShieldAlert } from 'lucide-react'
import type { DamageType } from '@/types/damage_type'

type ModalState =
  | { type: 'none' }
  | { type: 'create' }
  | { type: 'edit'; item: DamageType }
  | { type: 'delete'; item: DamageType }

export default function DamageTypesPage() {
  const [modal, setModal] = useState<ModalState>({ type: 'none' })
  const [formName, setFormName] = useState('')
  const [formFee, setFormFee] = useState('')
  const [formActive, setFormActive] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const { data: damageTypesData, isLoading, error: queryError, refetch } = useDamageTypesList()
  const items = damageTypesData?.items ?? []
  const createMutation = useCreateDamageType()
  const updateMutation = useUpdateDamageType()
  const deleteMutation = useDeleteDamageType()

  const openCreate = () => {
    setFormName('')
    setFormFee('')
    setFormActive(true)
    setError(null)
    setModal({ type: 'create' })
  }

  const openEdit = (item: DamageType) => {
    setFormName(item.name)
    setFormFee(String(item.default_fee_cents / 100))
    setFormActive(item.is_active)
    setError(null)
    setModal({ type: 'edit', item })
  }

  const closeModal = () => {
    setModal({ type: 'none' })
    setError(null)
  }

  const handleSubmit = () => {
    const feeCents = Math.round(parseFloat(formFee || '0') * 100)
    if (!formName.trim()) { setError('Le nom est requis'); return }
    if (isNaN(feeCents) || feeCents < 0) { setError('Montant invalide'); return }

    if (modal.type === 'create') {
      createMutation.mutate(
        { name: formName.trim(), default_fee_cents: feeCents },
        {
          onSuccess: () => closeModal(),
          onError: (err) => setError(normalizeError(err).message || 'Erreur lors de la création'),
        }
      )
    } else if (modal.type === 'edit') {
      updateMutation.mutate(
        {
          id: modal.item.id,
          data: { name: formName.trim(), default_fee_cents: feeCents, is_active: formActive },
        },
        {
          onSuccess: () => closeModal(),
          onError: (err) => setError(normalizeError(err).message || 'Erreur lors de la modification'),
        }
      )
    }
  }

  const active = items.filter((i) => i.is_active)
  const inactive = items.filter((i) => !i.is_active)

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2 min-w-0">
            <ShieldAlert className="w-6 h-6 text-primary-400" />
            Types de dommages
          </h1>
          <p className="text-dark-400 mt-1 text-sm">Gérez les types et tarifs par défaut pour les déclarations de dommages</p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Nouveau type
        </button>
      </div>

      {isLoading ? (
        <div className="card divide-y divide-dark-600 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-4">
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-36" />
                <div className="h-2 skel rounded w-52" />
              </div>
              <div className="h-6 skel rounded w-6 shrink-0" />
            </div>
          ))}
        </div>
      ) : queryError ? (
        <div className="card text-center py-12">
          <p className="text-red-400 mb-4">Erreur lors du chargement des types de dommage.</p>
          <button onClick={() => refetch()} className="btn-secondary text-sm">Réessayer</button>
        </div>
      ) : items.length === 0 ? (
        <div className="card text-center py-10 text-dark-400">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-dark-600" />
          <p>Aucun type de dommage configuré</p>
          <p className="text-sm mt-1">Créez des types pour accélérer les déclarations lors des retours</p>
        </div>
      ) : (
        <div className="space-y-4">
          {active.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wider mb-2 px-1">
                Actifs ({active.length})
              </h2>
              <div className="card p-0 divide-y divide-dark-600">
                {active.map((item) => (
                  <DamageTypeRow key={item.id} item={item} onEdit={openEdit} onDelete={(i) => { setError(null); setModal({ type: 'delete', item: i }) }} />
                ))}
              </div>
            </section>
          )}

          {inactive.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wider mb-2 px-1">
                Inactifs ({inactive.length})
              </h2>
              <div className="card p-0 divide-y divide-dark-600 opacity-60">
                {inactive.map((item) => (
                  <DamageTypeRow key={item.id} item={item} onEdit={openEdit} onDelete={(i) => { setError(null); setModal({ type: 'delete', item: i }) }} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      {/* Modal Créer / Modifier */}
      {(modal.type === 'create' || modal.type === 'edit') && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="modal-panel w-full max-w-md p-6 space-y-4">
            <h2 className="text-lg font-bold">
              {modal.type === 'create' ? 'Nouveau type de dommage' : 'Modifier le type'}
            </h2>

            {error && (
              <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2">{error}</p>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">Nom du type *</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="input"
                  placeholder="Ex: Casse, Rayure, Tache…"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm text-dark-400 mb-1">Tarif par défaut (€)</label>
                <input
                  type="number"
                  value={formFee}
                  onChange={(e) => setFormFee(e.target.value)}
                  className="input"
                  placeholder="0.00 — laisser vide pour saisie manuelle"
                  min="0"
                  step="0.01"
                />
                <p className="text-xs text-dark-500 mt-1">0 = montant à saisir lors de la déclaration</p>
              </div>

              {modal.type === 'edit' && (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formActive}
                    onChange={(e) => setFormActive(e.target.checked)}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-sm">Type actif</span>
                </label>
              )}
            </div>

            <div className="flex gap-4 pt-2">
              <button onClick={closeModal} className="btn-secondary flex-1">Annuler</button>
              <button
                onClick={handleSubmit}
                disabled={createMutation.isPending || updateMutation.isPending}
                className="btn-primary flex-1"
              >
                {modal.type === 'create' ? 'Créer' : 'Enregistrer'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Supprimer */}
      {modal.type === 'delete' && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="modal-panel w-full max-w-md p-6 space-y-4">
            <h2 className="text-lg font-bold text-red-400">Supprimer le type</h2>
            <p className="text-sm text-dark-300">
              Supprimer <strong className="">«&nbsp;{modal.item.name}&nbsp;»</strong> ? Cette action est irréversible.
            </p>
            {error && (
              <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2">{error}</p>
            )}
            <div className="flex gap-4">
              <button onClick={closeModal} className="btn-secondary flex-1">Annuler</button>
              <button
                onClick={() =>
                  deleteMutation.mutate(modal.item.id, {
                    onSuccess: () => closeModal(),
                    onError: (err) => setError(normalizeError(err).message || 'Erreur lors de la suppression'),
                  })
                }
                disabled={deleteMutation.isPending}
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

function DamageTypeRow({
  item,
  onEdit,
  onDelete,
}: {
  item: DamageType
  onEdit: (item: DamageType) => void
  onDelete: (item: DamageType) => void
}) {
  return (
    <div className="flex items-center gap-4 px-4 py-4">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{item.name}</p>
        <p className="text-xs text-dark-400">
          {item.default_fee_cents > 0 ? `Tarif : ${formatCents(item.default_fee_cents)}` : 'Montant libre'}
        </p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={() => onEdit(item)}
          className="p-1.5 rounded-lg hover:bg-dark-600 text-dark-400 hover:text-dark-50 transition-colors"
        >
          <Pencil className="w-4 h-4" />
        </button>
        <button
          onClick={() => onDelete(item)}
          className="p-1.5 rounded-lg hover:bg-dark-600 text-dark-400 hover:text-red-400 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
