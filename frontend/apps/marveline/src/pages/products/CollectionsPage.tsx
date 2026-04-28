import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { FolderOpen, Plus, Pencil, Trash2, ChevronRight, ToggleLeft, ToggleRight } from 'lucide-react'
import {
  useCollectionsList,
  useCreateCollection,
  useUpdateCollection,
  useDeleteCollection,
} from '@/api/queries/useCollections'
import type { Collection, CollectionCreate, CollectionUpdate } from '@/types/collection'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { normalizeError } from '@shared/errors/normalizer'

type FormState = { name: string; description: string; is_active: boolean }
const DEFAULT_FORM: FormState = { name: '', description: '', is_active: true }

export default function CollectionsPage() {
  const navigate = useNavigate()
  const { data, isLoading, error: queryError, refetch } = useCollectionsList({ limit: 100 })
  const createCollection = useCreateCollection()
  const updateCollection = useUpdateCollection()
  const deleteCollection = useDeleteCollection()

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Collection | null>(null)
  const [form, setForm] = useState<FormState>(DEFAULT_FORM)
  const [error, setError] = useState<string | null>(null)

  const collections = data?.items ?? []

  const openAdd = () => {
    setEditing(null)
    setForm(DEFAULT_FORM)
    setShowForm(true)
    setError(null)
  }

  const openEdit = (col: Collection) => {
    setEditing(col)
    setForm({ name: col.name, description: col.description ?? '', is_active: col.is_active })
    setShowForm(true)
    setError(null)
  }

  const handleSubmit = () => {
    if (!form.name.trim()) { setError('Le nom est requis.'); return }
    setError(null)

    if (editing) {
      const data: CollectionUpdate = {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        is_active: form.is_active,
      }
      updateCollection.mutate(
        { id: editing.id, data },
        {
          onSuccess: () => { setShowForm(false); setEditing(null) },
          onError: (err) => setError(
            normalizeError(err).message || 'Erreur lors de la mise à jour.'
          ),
        }
      )
    } else {
      const data: CollectionCreate = {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        is_active: form.is_active,
      }
      createCollection.mutate(data, {
        onSuccess: () => setShowForm(false),
        onError: (err) => setError(
          normalizeError(err).message || 'Erreur lors de la création.'
        ),
      })
    }
  }

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FolderOpen className="w-5 h-5 text-purple-400" />
          <PageHeader title="Collections" />
          <span className="text-sm text-dark-400">({data?.total ?? 0})</span>
        </div>
        <button
          onClick={openAdd}
          className="flex items-center gap-2 bg-gold-600 hover:bg-gold-700 text-white text-sm font-medium px-4 py-2 rounded-lg"
        >
          <Plus className="w-4 h-4" /> Nouvelle
        </button>
      </div>

      {/* Formulaire inline */}
      {showForm && (
        <div className="card space-y-4 border border-purple-700/40">
          <p className="text-sm font-medium">
            {editing ? 'Modifier la collection' : 'Nouvelle collection'}
          </p>
          <div>
            <label className="block text-xs text-dark-400 mb-1">Nom</label>
            <input
              type="text"
              placeholder="Nom de la collection…"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="input"
            />
          </div>
          <div>
            <label className="block text-xs text-dark-400 mb-1">Description</label>
            <textarea
              placeholder="Description optionnelle…"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              rows={2}
              className="input resize-none"
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setForm((f) => ({ ...f, is_active: !f.is_active }))}
              className="text-dark-400 hover:text-dark-50"
            >
              {form.is_active
                ? <ToggleRight className="w-5 h-5 text-green-400" />
                : <ToggleLeft className="w-5 h-5" />}
            </button>
            <span className="text-xs text-dark-400">{form.is_active ? 'Active' : 'Inactive'}</span>
          </div>
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={() => { setShowForm(false); setEditing(null); setError(null) }}
              className="flex-1 text-sm text-dark-400 hover:text-dark-50 py-2 rounded-lg border border-dark-600"
            >
              Annuler
            </button>
            <button
              onClick={handleSubmit}
              disabled={createCollection.isPending || updateCollection.isPending}
              className="flex-1 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium py-2 rounded-lg disabled:opacity-50"
            >
              {(createCollection.isPending || updateCollection.isPending) ? 'Enregistrement…' : 'Enregistrer'}
            </button>
          </div>
        </div>
      )}

      {/* Liste */}
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card flex items-center gap-4">
              <div className="w-8 h-8 skel rounded-lg shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-36" />
                <div className="h-2 skel rounded w-52" />
              </div>
              <div className="flex gap-2 shrink-0">
                <div className="w-7 h-7 skel rounded" />
                <div className="w-7 h-7 skel rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : queryError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : collections.length === 0 ? (
        <div className="text-center text-dark-400 text-sm py-8">
          Aucune collection — créez-en une pour regrouper vos produits
        </div>
      ) : (
        <div className="space-y-2">
          {collections.map((col) => (
            <div key={col.id} className="card flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium truncate">{col.name}</p>
                  {!col.is_active && (
                    <span className="text-xs text-dark-500 bg-dark-900 px-1.5 py-0.5 rounded">Inactive</span>
                  )}
                </div>
                {col.description && (
                  <p className="text-dark-400 text-xs line-clamp-2 mt-0.5">{col.description}</p>
                )}
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => navigate({ to: '/catalogue/collections/$id', params: { id: String(col.id) } })}
                  className="p-1.5 hover:bg-dark-600 rounded text-dark-400 hover:text-dark-50 min-h-[44px] min-w-[44px] flex items-center justify-center"
                  title="Voir les produits"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
                <button
                  onClick={() => openEdit(col)}
                  className="p-1.5 hover:bg-dark-600 rounded text-dark-400 hover:text-dark-50 min-h-[44px] min-w-[44px] flex items-center justify-center"
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteCollection.mutate(col.id)}
                  disabled={deleteCollection.isPending}
                  className="p-1.5 hover:bg-dark-600 rounded text-dark-400 hover:text-red-400 disabled:opacity-50 min-h-[44px] min-w-[44px] flex items-center justify-center"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
