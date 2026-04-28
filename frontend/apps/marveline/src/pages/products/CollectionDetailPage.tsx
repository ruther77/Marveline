import { useState } from 'react'
import { useParams, useNavigate } from '@tanstack/react-router'
import { ArrowLeft, FolderOpen, X, Plus, Pencil, Trash2 } from 'lucide-react'
import {
  useCollectionDetail,
  useUpdateCollection,
  useDeleteCollection,
  useAddProductsToCollection,
  useRemoveProductFromCollection,
} from '@/api/queries/useCollections'
import { Modal } from '@shared/components/ui/Modal'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { CataloguePickerModal } from '@/components/catalogue/CataloguePickerModal'
import type { CollectionUpdate } from '@/types/collection'
import { normalizeError } from '@shared/errors/normalizer'

export default function CollectionDetailPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const navigate = useNavigate()
  const collectionId = parseInt(id, 10)

  const { data: collection, isLoading, error, refetch } = useCollectionDetail(collectionId)
  const removeProduct = useRemoveProductFromCollection()
  const updateCollection = useUpdateCollection()
  const deleteCollection = useDeleteCollection()
  const addProducts = useAddProductsToCollection()

  const [editOpen, setEditOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [editForm, setEditForm] = useState<CollectionUpdate>({})
  const [editError, setEditError] = useState('')

  const openEdit = () => {
    if (!collection) return
    setEditForm({ name: collection.name, description: collection.description ?? '', is_active: collection.is_active })
    setEditError('')
    setEditOpen(true)
  }

  const handleUpdate = async () => {
    setEditError('')
    if (!editForm.name?.trim()) { setEditError('Nom requis.'); return }
    try {
      await updateCollection.mutateAsync({ id: collectionId, data: editForm })
      setEditOpen(false)
    } catch (err) {
      setEditError(normalizeError(err).message || 'Erreur lors de la mise à jour.')
    }
  }

  const handleDelete = async () => {
    try {
      await deleteCollection.mutateAsync(collectionId)
      navigate({ to: '/catalogue/collections' })
    } catch {
      // ignore, user can retry
    }
  }

  if (isLoading) return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6 animate-pulse">
      <div className="flex items-center gap-4">
        <div className="w-9 h-9 skel rounded" />
        <div className="space-y-2">
          <div className="h-5 skel rounded w-40" />
          <div className="h-3 skel rounded w-28" />
        </div>
      </div>
      <div className="card divide-y divide-dark-600">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-4">
            <div className="w-10 h-10 skel rounded-lg shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-3 skel rounded w-36" />
              <div className="h-2 skel rounded w-20" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
  if (error) return <ErrorState onRetry={() => refetch()} />
  if (!collection) return <div className="p-6 text-center text-dark-400">Collection introuvable.</div>

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate({ to: '/catalogue/collections' })}
          className="p-2 hover:bg-dark-600 rounded text-dark-400"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <FolderOpen className="w-5 h-5 text-purple-400" />
            <h1 className="text-xl font-semibold truncate">{collection.name}</h1>
            {!collection.is_active && (
              <span className="text-xs text-dark-500 bg-dark-900 px-1.5 py-0.5 rounded">Inactive</span>
            )}
          </div>
          {collection.description && (
            <p className="text-sm text-dark-400 mt-0.5">{collection.description}</p>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={openEdit}
            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-dark-600 text-dark-400 hover:text-dark-100 transition-colors"
            title="Modifier"
          >
            <Pencil className="w-4 h-4" />
          </button>
          <button
            onClick={() => setPickerOpen(true)}
            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-dark-600 text-dark-400 hover:text-primary-400 transition-colors"
            title="Ajouter un produit"
          >
            <Plus className="w-4 h-4" />
          </button>
          <button
            onClick={() => setConfirmDelete(true)}
            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-red-500/10 text-dark-400 hover:text-red-400 transition-colors"
            title="Supprimer la collection"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Produits */}
      <div className="space-y-1">
        <p className="text-xs text-dark-500 uppercase tracking-wide mb-2">
          {collection.products.length} produit{collection.products.length !== 1 ? 's' : ''}
        </p>
        {collection.products.length === 0 ? (
          <div className="card text-center text-dark-400 text-sm py-8">
            <p>Aucun produit dans cette collection.</p>
            <button
              onClick={() => setPickerOpen(true)}
              className="mt-4 btn-primary text-sm"
            >
              Ajouter des produits
            </button>
          </div>
        ) : (
          <div className="card divide-y divide-dark-600 p-0">
            {collection.products.map((p) => (
              <div key={p.id} className="flex items-center justify-between gap-4 px-4 py-4">
                <div>
                  <p className="text-sm">{p.name}</p>
                  {p.reference && <p className="text-dark-500 text-xs">{p.reference}</p>}
                </div>
                <button
                  onClick={() => removeProduct.mutate({ collectionId, productId: p.id })}
                  disabled={removeProduct.isPending}
                  className="p-1.5 hover:bg-dark-600 rounded text-dark-500 hover:text-red-400 disabled:opacity-50"
                  title="Retirer de la collection"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal édition */}
      <Modal
        isOpen={editOpen}
        onClose={() => setEditOpen(false)}
        title="Modifier la collection"
        footer={
          <div className="flex justify-end gap-4">
            <button onClick={() => setEditOpen(false)} className="px-4 py-2 text-sm text-dark-400 hover:text-dark-100">
              Annuler
            </button>
            <button
              onClick={handleUpdate}
              disabled={updateCollection.isPending}
              className="btn btn-primary"
            >
              {updateCollection.isPending ? 'Mise à jour…' : 'Enregistrer'}
            </button>
          </div>
        }
      >
        <div className="p-1 space-y-4">
          {editError && (
            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {editError}
            </div>
          )}
          <div>
            <label className="block text-dark-300 text-xs mb-1">Nom *</label>
            <input
              className="input"
              value={editForm.name ?? ''}
              onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-dark-300 text-xs mb-1">Description</label>
            <textarea
              className="input w-full resize-none"
              rows={2}
              value={editForm.description ?? ''}
              onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={editForm.is_active ?? true}
              onChange={(e) => setEditForm((f) => ({ ...f, is_active: e.target.checked }))}
              className="rounded"
            />
            <span className="text-sm">Active</span>
          </label>
        </div>
      </Modal>

      {/* Modal confirmation suppression */}
      <Modal
        isOpen={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Supprimer la collection"
        footer={
          <div className="flex justify-end gap-4">
            <button onClick={() => setConfirmDelete(false)} className="px-4 py-2 text-sm text-dark-400 hover:text-dark-100">
              Annuler
            </button>
            <button
              onClick={handleDelete}
              disabled={deleteCollection.isPending}
              className="btn btn-danger"
            >
              {deleteCollection.isPending ? 'Suppression…' : 'Supprimer'}
            </button>
          </div>
        }
      >
        <p className="p-1 text-sm text-dark-400">
          Supprimer <span className="font-semibold">{collection.name}</span> ?
          Cette action est irréversible.
        </p>
      </Modal>

      {/* Catalogue picker */}
      <CataloguePickerModal
        isOpen={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(line) => {
          if (line.product_id) {
            addProducts.mutate({ collectionId, productIds: [line.product_id] })
          }
          setPickerOpen(false)
        }}
      />
    </div>
  )
}
