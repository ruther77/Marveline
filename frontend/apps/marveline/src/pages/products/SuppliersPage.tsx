import { PageHeader } from '@/components/PageHeader'
import { useState, useEffect } from 'react'
import { Truck, Plus, Pencil, Trash2, Phone, Mail, MapPin } from 'lucide-react'
import { useSuppliers, useSupplierMutations } from '@/api/queries/useSuppliers'
import { Modal } from '@shared/components/ui/Modal'
import { ErrorState } from '@shared/components/ui/EmptyState'
import type { Supplier, SupplierCreate, SupplierUpdate } from '@/types/supplier'
import { normalizeError } from '@shared/errors/normalizer'

// ── Formulaire ─────────────────────────────────────────────────────────────

interface FormState {
  name: string
  contact_name: string
  email: string
  phone: string
  address: string
  notes: string
}

const EMPTY: FormState = {
  name: '',
  contact_name: '',
  email: '',
  phone: '',
  address: '',
  notes: '',
}

function toPayload(f: FormState): SupplierCreate {
  return {
    name: f.name.trim(),
    contact_name: f.contact_name.trim() || undefined,
    email: f.email.trim() || undefined,
    phone: f.phone.trim() || undefined,
    address: f.address.trim() || undefined,
    notes: f.notes.trim() || undefined,
  }
}

interface SupplierFormModalProps {
  isOpen: boolean
  onClose: () => void
  initial?: Supplier | null
}

function SupplierFormModal({ isOpen, onClose, initial }: SupplierFormModalProps) {
  const { create, update } = useSupplierMutations()
  const isEdit = !!initial

  const [form, setForm] = useState<FormState>(EMPTY)
  const [error, setError] = useState('')

  useEffect(() => {
    if (isOpen) {
      setError('')
      setForm(
        initial
          ? {
              name: initial.name,
              contact_name: initial.contact_name ?? '',
              email: initial.email ?? '',
              phone: initial.phone ?? '',
              address: initial.address ?? '',
              notes: initial.notes ?? '',
            }
          : EMPTY
      )
    }
  }, [isOpen, initial])

  const set = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((prev) => ({ ...prev, [k]: e.target.value }))

  const handleSubmit = async () => {
    if (!form.name.trim()) { setError('Le nom est requis.'); return }
    setError('')
    try {
      if (isEdit && initial) {
        const payload: SupplierUpdate = toPayload(form)
        await update.mutateAsync({ id: initial.id, data: payload })
      } else {
        await create.mutateAsync(toPayload(form))
      }
      onClose()
    } catch (err) {
      setError(normalizeError(err).message || 'Une erreur est survenue.')
    }
  }

  const isPending = create.isPending || update.isPending

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Modifier le fournisseur' : 'Nouveau fournisseur'}
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={onClose} className="px-4 py-2 text-sm text-dark-300 hover:text-dark-50">
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={isPending}
            className="px-4 py-2 text-sm bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium rounded-lg disabled:opacity-50"
          >
            {isPending ? 'Enregistrement…' : isEdit ? 'Modifier' : 'Créer'}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        {error && (
          <p className="text-red-400 text-sm bg-red-900/20 border border-red-700/30 rounded-lg px-4 py-2">
            {error}
          </p>
        )}

        <div>
          <label className="block text-sm text-dark-300 mb-1">Nom *</label>
          <input
            type="text"
            value={form.name}
            onChange={set('name')}
            className="input"
            placeholder="Nom du fournisseur"
          />
        </div>

        <div>
          <label className="block text-sm text-dark-300 mb-1">Contact</label>
          <input
            type="text"
            value={form.contact_name}
            onChange={set('contact_name')}
            className="input"
            placeholder="Nom du contact"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-dark-300 mb-1">Email</label>
            <input
              type="email"
              value={form.email}
              onChange={set('email')}
              className="input"
              placeholder="contact@fournisseur.fr"
            />
          </div>
          <div>
            <label className="block text-sm text-dark-300 mb-1">Téléphone</label>
            <input
              type="tel"
              value={form.phone}
              onChange={set('phone')}
              className="input"
              placeholder="06 XX XX XX XX"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm text-dark-300 mb-1">Adresse</label>
          <input
            type="text"
            value={form.address}
            onChange={set('address')}
            className="input"
            placeholder="Adresse complète"
          />
        </div>

        <div>
          <label className="block text-sm text-dark-300 mb-1">Notes</label>
          <textarea
            value={form.notes}
            onChange={set('notes')}
            rows={3}
            className="input resize-none"
            placeholder="Informations complémentaires…"
          />
        </div>
      </div>
    </Modal>
  )
}

// ── Modal suppression ───────────────────────────────────────────────────────

interface DeleteModalProps {
  supplier: Supplier | null
  onClose: () => void
}

function DeleteModal({ supplier, onClose }: DeleteModalProps) {
  const { remove } = useSupplierMutations()
  const [error, setError] = useState('')

  const handleConfirm = async () => {
    if (!supplier) return
    setError('')
    try {
      await remove.mutateAsync(supplier.id)
      onClose()
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur lors de la suppression.')
    }
  }

  return (
    <Modal
      isOpen={!!supplier}
      onClose={onClose}
      title="Supprimer le fournisseur"
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={onClose} className="px-4 py-2 text-sm text-dark-300 hover:text-dark-50">
            Annuler
          </button>
          <button
            onClick={handleConfirm}
            disabled={remove.isPending}
            className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white font-medium rounded-lg disabled:opacity-50"
          >
            {remove.isPending ? 'Suppression…' : 'Supprimer'}
          </button>
        </div>
      }
    >
      {error && (
        <p className="text-red-400 text-sm mb-4">{error}</p>
      )}
      <p className="text-dark-200 text-sm">
        Supprimer{' '}
        <span className="font-medium">{supplier?.name}</span> ? Cette action est
        irréversible.
      </p>
    </Modal>
  )
}

// ── Page principale ─────────────────────────────────────────────────────────

export default function SuppliersPage() {
  const { data: rawSuppliers, isLoading, error, refetch } = useSuppliers()
  const suppliers = Array.isArray(rawSuppliers) ? rawSuppliers : []
  const [createOpen, setCreateOpen] = useState(false)
  const [editing, setEditing] = useState<Supplier | null>(null)
  const [deleting, setDeleting] = useState<Supplier | null>(null)

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-4">
          <Truck className="w-6 h-6 text-gold-400" />
          <PageHeader title="Fournisseurs" />
          {suppliers.length > 0 && (
            <span className="text-sm text-dark-400">({suppliers.length})</span>
          )}
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm px-4 py-2 rounded-lg"
        >
          <Plus className="w-4 h-4" />
          Nouveau fournisseur
        </button>
      </div>

      {/* Contenu */}
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card flex items-center gap-4">
              <div className="w-10 h-10 skel rounded-lg shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-40" />
                <div className="h-2 skel rounded w-56" />
              </div>
              <div className="flex gap-2 shrink-0">
                <div className="w-7 h-7 skel rounded" />
                <div className="w-7 h-7 skel rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorState onRetry={() => refetch()} />
      ) : suppliers.length === 0 ? (
        <div className="card text-center py-12">
          <Truck className="w-10 h-10 text-dark-500 mx-auto mb-4" />
          <p className="font-medium">Aucun fournisseur</p>
          <p className="text-dark-400 text-sm mt-1">
            Ajoutez vos fournisseurs pour les associer à vos produits.
          </p>
          <button
            onClick={() => setCreateOpen(true)}
            className="mt-4 inline-flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm px-4 py-2 rounded-lg"
          >
            <Plus className="w-4 h-4" />
            Ajouter un fournisseur
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {suppliers.map((s) => (
            <div
              key={s.id}
              className="card p-4 flex flex-col gap-4 hover:shadow-md transition-shadow"
            >
              {/* Nom + actions */}
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{s.name}</p>
                  {s.contact_name && (
                    <p className="text-dark-400 text-xs mt-0.5">{s.contact_name}</p>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => setEditing(s)}
                    className="p-1.5 hover:bg-dark-600 rounded text-dark-400 hover:text-dark-50 min-h-[44px] min-w-[44px] flex items-center justify-center"
                    aria-label="Modifier"
                  >
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setDeleting(s)}
                    className="p-1.5 hover:bg-dark-600 rounded text-dark-400 hover:text-red-400 min-h-[44px] min-w-[44px] flex items-center justify-center"
                    aria-label="Supprimer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Coordonnées */}
              <div className="space-y-1.5">
                {s.email && (
                  <a
                    href={`mailto:${s.email}`}
                    className="flex items-center gap-2 text-xs text-dark-300 hover:text-gold-400"
                  >
                    <Mail className="w-3.5 h-3.5 shrink-0" />
                    {s.email}
                  </a>
                )}
                {s.phone && (
                  <a
                    href={`tel:${s.phone}`}
                    className="flex items-center gap-2 text-xs text-dark-300 hover:text-gold-400"
                  >
                    <Phone className="w-3.5 h-3.5 shrink-0" />
                    {s.phone}
                  </a>
                )}
                {s.address && (
                  <div className="flex items-start gap-2 text-xs text-dark-400">
                    <MapPin className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    <span>{s.address}</span>
                  </div>
                )}
              </div>

              {/* Notes */}
              {s.notes && (
                <p className="text-xs text-dark-400 border-t border-dark-600 pt-2 leading-relaxed">
                  {s.notes}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Modals */}
      <SupplierFormModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
      />
      <SupplierFormModal
        isOpen={!!editing}
        onClose={() => setEditing(null)}
        initial={editing}
      />
      <DeleteModal
        supplier={deleting}
        onClose={() => setDeleting(null)}
      />
    </div>
  )
}
