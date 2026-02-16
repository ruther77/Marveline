import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { featureFlagsApi } from '@/api/featureFlags'
import type { FeatureFlagList, FeatureFlagCreate, FeatureFlagUpdate } from '@/types/featureFlag'
import { PageHeader } from '@/components/ui/Breadcrumb'
import { Badge } from '@/components/ui/Badge'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { DeleteConfirm } from '@/components/ui/ConfirmDialog'
import { cn } from '@/lib/utils'
import {
  ToggleLeft,
  Plus,
  Pencil,
  Trash2,
  Loader2,
  Flag,
  Users,
  Percent,
} from 'lucide-react'

export default function FeatureFlagsPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingFlag, setEditingFlag] = useState<FeatureFlagList | null>(null)
  const [deleteFlag, setDeleteFlag] = useState<FeatureFlagList | null>(null)

  // Form state
  const [formName, setFormName] = useState('')
  const [formDesc, setFormDesc] = useState('')
  const [formEnabled, setFormEnabled] = useState(false)
  const [formRollout, setFormRollout] = useState(100)
  const [formTenants, setFormTenants] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['feature-flags', page],
    queryFn: () => featureFlagsApi.list(page, 50),
  })

  const flags = data?.items || []
  const totalPages = data?.pages || 1

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      featureFlagsApi.toggle(id, enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['feature-flags'] }),
  })

  const createMutation = useMutation({
    mutationFn: (data: FeatureFlagCreate) => featureFlagsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feature-flags'] })
      closeModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: FeatureFlagUpdate }) =>
      featureFlagsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feature-flags'] })
      closeModal()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => featureFlagsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feature-flags'] })
      setDeleteFlag(null)
    },
  })

  const openCreate = () => {
    setEditingFlag(null)
    setFormName('')
    setFormDesc('')
    setFormEnabled(false)
    setFormRollout(100)
    setFormTenants('')
    setModalOpen(true)
  }

  const openEdit = (flag: FeatureFlagList) => {
    setEditingFlag(flag)
    setFormName(flag.name)
    setFormDesc(flag.description || '')
    setFormEnabled(flag.is_enabled)
    setFormRollout(flag.rollout_pct)
    setFormTenants(flag.target_tenants ? flag.target_tenants.join(', ') : '')
    setModalOpen(true)
  }

  const closeModal = () => {
    setModalOpen(false)
    setEditingFlag(null)
  }

  const handleSubmit = () => {
    const tenants = formTenants.trim()
      ? formTenants.split(',').map((t) => parseInt(t.trim(), 10)).filter((n) => !isNaN(n))
      : null

    if (editingFlag) {
      updateMutation.mutate({
        id: editingFlag.id,
        data: {
          description: formDesc || undefined,
          is_enabled: formEnabled,
          rollout_pct: formRollout,
          target_tenants: tenants,
        },
      })
    } else {
      createMutation.mutate({
        name: formName,
        description: formDesc || undefined,
        is_enabled: formEnabled,
        rollout_pct: formRollout,
        target_tenants: tenants,
      })
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  return (
    <div className="space-y-6">
      <PageHeader
        title="Feature Flags"
        subtitle="Gestion des fonctionnalites et rollout progressif"
        breadcrumbs={[{ label: 'Admin' }, { label: 'Feature Flags' }]}
        actions={
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Nouveau flag
          </button>
        }
      />

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Nom</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Description</th>
                <th className="text-center py-3 px-4 text-sm font-medium text-dark-400">Actif</th>
                <th className="text-center py-3 px-4 text-sm font-medium text-dark-400">Rollout</th>
                <th className="text-center py-3 px-4 text-sm font-medium text-dark-400">Tenants</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-dark-400">
                    <Loader2 className="w-5 h-5 animate-spin inline-block mr-2" />
                    Chargement...
                  </td>
                </tr>
              ) : flags.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center">
                    <Flag className="w-8 h-8 text-dark-600 mx-auto mb-3" />
                    <p className="text-dark-400">Aucun feature flag</p>
                    <button onClick={openCreate} className="text-primary-400 text-sm mt-2 hover:underline">
                      Creer le premier
                    </button>
                  </td>
                </tr>
              ) : (
                flags.map((flag) => (
                  <tr key={flag.id} className="border-b border-dark-700/50 hover:bg-dark-700/30">
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm text-white">{flag.name}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm text-dark-400 max-w-xs truncate block">
                        {flag.description || '-'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={() =>
                          toggleMutation.mutate({ id: flag.id, enabled: !flag.is_enabled })
                        }
                        disabled={toggleMutation.isPending}
                        className={cn(
                          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                          flag.is_enabled ? 'bg-green-600' : 'bg-dark-600'
                        )}
                      >
                        <span
                          className={cn(
                            'inline-block h-4 w-4 rounded-full bg-white transition-transform',
                            flag.is_enabled ? 'translate-x-6' : 'translate-x-1'
                          )}
                        />
                      </button>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <Percent className="w-3.5 h-3.5 text-dark-500" />
                        <span className={cn(
                          'text-sm font-medium',
                          flag.rollout_pct === 100 ? 'text-green-400' : 'text-yellow-400'
                        )}>
                          {flag.rollout_pct}%
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {flag.target_tenants === null ? (
                        <Badge variant="default" size="sm">Tous</Badge>
                      ) : flag.target_tenants.length === 0 ? (
                        <Badge variant="danger" size="sm">Aucun</Badge>
                      ) : (
                        <div className="flex items-center justify-center gap-1">
                          <Users className="w-3.5 h-3.5 text-dark-500" />
                          <Badge variant="info" size="sm">
                            {flag.target_tenants.length}
                          </Badge>
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => openEdit(flag)}
                          className="p-2 text-dark-400 hover:text-white hover:bg-dark-700 rounded-lg transition-colors"
                          title="Modifier"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setDeleteFlag(flag)}
                          className="p-2 text-dark-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                          title="Supprimer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-dark-700">
            <p className="text-sm text-dark-400">
              Page {page} sur {totalPages}
              {data?.total != null && ` (${data.total} flags)`}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-ghost p-2 disabled:opacity-50"
              >
                Precedent
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn-ghost p-2 disabled:opacity-50"
              >
                Suivant
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={closeModal}
        title={editingFlag ? 'Modifier le flag' : 'Nouveau feature flag'}
        size="lg"
        footer={
          <ModalFooter
            onCancel={closeModal}
            onConfirm={handleSubmit}
            confirmText={editingFlag ? 'Enregistrer' : 'Creer'}
            loading={isSaving}
          />
        }
      >
        <div className="space-y-4">
          {/* Name (read-only on edit) */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Nom technique
            </label>
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="enable_new_checkout"
              pattern="^[a-z][a-z0-9_]*$"
              className="input w-full font-mono"
              disabled={!!editingFlag}
            />
            <p className="text-xs text-dark-500 mt-1">
              Lettres minuscules, chiffres et underscores (ex: enable_dark_mode)
            </p>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Description
            </label>
            <input
              type="text"
              value={formDesc}
              onChange={(e) => setFormDesc(e.target.value)}
              placeholder="Active le nouveau parcours de paiement"
              className="input w-full"
            />
          </div>

          {/* Enabled toggle */}
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm font-medium text-white">Actif</p>
              <p className="text-xs text-dark-500">Interrupteur global (kill switch)</p>
            </div>
            <button
              type="button"
              onClick={() => setFormEnabled(!formEnabled)}
              className={cn(
                'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                formEnabled ? 'bg-green-600' : 'bg-dark-600'
              )}
            >
              <span
                className={cn(
                  'inline-block h-4 w-4 rounded-full bg-white transition-transform',
                  formEnabled ? 'translate-x-6' : 'translate-x-1'
                )}
              />
            </button>
          </div>

          {/* Rollout percentage */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Rollout ({formRollout}%)
            </label>
            <input
              type="range"
              min={0}
              max={100}
              value={formRollout}
              onChange={(e) => setFormRollout(Number(e.target.value))}
              className="w-full accent-primary-500"
            />
            <div className="flex justify-between text-xs text-dark-500 mt-1">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>

          {/* Target tenants */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Tenants cibles (optionnel)
            </label>
            <input
              type="text"
              value={formTenants}
              onChange={(e) => setFormTenants(e.target.value)}
              placeholder="1, 2, 5"
              className="input w-full"
            />
            <p className="text-xs text-dark-500 mt-1">
              Laisser vide pour tous les tenants. IDs separes par des virgules.
            </p>
          </div>
        </div>
      </Modal>

      {/* Delete confirmation */}
      <DeleteConfirm
        isOpen={!!deleteFlag}
        onClose={() => setDeleteFlag(null)}
        onConfirm={() => deleteFlag && deleteMutation.mutate(deleteFlag.id)}
        itemName={deleteFlag?.name}
        loading={deleteMutation.isPending}
      />
    </div>
  )
}
