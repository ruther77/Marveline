import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiKeysApi } from '@/api/apiKeys'
import type { ApiKeyList, ApiKeyCreate, ApiKeyCreated } from '@/types/apiKey'
import { PageHeader } from '@/components/ui/Breadcrumb'
import { Badge } from '@/components/ui/Badge'
import { Modal, ModalFooter } from '@/components/ui/Modal'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { formatDate } from '@/lib/utils'
import { cn } from '@/lib/utils'
import {
  Key,
  Plus,
  Trash2,
  RotateCw,
  Copy,
  Check,
  Loader2,
  Eye,
  EyeOff,
  AlertTriangle,
} from 'lucide-react'

const AVAILABLE_SCOPES = [
  { group: 'Produits', scopes: ['products:read', 'products:write', 'products:delete'] },
  { group: 'Categories', scopes: ['categories:read', 'categories:write', 'categories:delete'] },
  { group: 'Formules', scopes: ['bundles:read', 'bundles:write', 'bundles:delete'] },
  { group: 'Reservations', scopes: ['reservations:read', 'reservations:write', 'reservations:delete'] },
  { group: 'Factures', scopes: ['invoices:read', 'invoices:write'] },
  { group: 'Clients', scopes: ['customers:read', 'customers:write', 'customers:delete'] },
  { group: 'Inventaire', scopes: ['inventory:read', 'inventory:write'] },
  { group: 'Utilisateurs', scopes: ['users:read', 'users:write', 'users:admin'] },
  { group: 'Audit', scopes: ['audit:read'] },
]

export default function ApiKeysPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [showInactive, setShowInactive] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteKey, setDeleteKey] = useState<ApiKeyList | null>(null)
  const [rotateKey, setRotateKey] = useState<ApiKeyList | null>(null)
  const [newKey, setNewKey] = useState<ApiKeyCreated | null>(null)
  const [copied, setCopied] = useState(false)

  // Create form state
  const [formName, setFormName] = useState('')
  const [formScopes, setFormScopes] = useState<string[]>([])
  const [formRateLimit, setFormRateLimit] = useState('1000')
  const [formExpires, setFormExpires] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['api-keys', page, showInactive],
    queryFn: () => apiKeysApi.list(page, 50, showInactive),
  })

  const keys = data?.items || []
  const totalPages = data?.pages || 1

  const createMutation = useMutation({
    mutationFn: (data: ApiKeyCreate) => apiKeysApi.create(data),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      setCreateOpen(false)
      setNewKey(created)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiKeysApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      setDeleteKey(null)
    },
  })

  const rotateMutation = useMutation({
    mutationFn: (id: number) => apiKeysApi.rotate(id),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      setRotateKey(null)
      setNewKey(created)
    },
  })

  const openCreate = () => {
    setFormName('')
    setFormScopes([])
    setFormRateLimit('1000')
    setFormExpires('')
    setCreateOpen(true)
  }

  const handleCreate = () => {
    const rateLimit = formRateLimit.trim() ? parseInt(formRateLimit, 10) : null
    createMutation.mutate({
      name: formName,
      scopes: formScopes,
      rate_limit: rateLimit && rateLimit > 0 ? rateLimit : null,
      expires_at: formExpires ? new Date(formExpires).toISOString() : null,
    })
  }

  const toggleScope = (scope: string) => {
    setFormScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    )
  }

  const toggleGroupScopes = (scopes: string[]) => {
    const allSelected = scopes.every((s) => formScopes.includes(s))
    if (allSelected) {
      setFormScopes((prev) => prev.filter((s) => !scopes.includes(s)))
    } else {
      setFormScopes((prev) => [...new Set([...prev, ...scopes])])
    }
  }

  const copyKey = async (key: string) => {
    await navigator.clipboard.writeText(key)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="API Keys"
        subtitle="Cles d'acces machine-to-machine (M2M)"
        breadcrumbs={[{ label: 'Admin' }, { label: 'API Keys' }]}
        actions={
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Nouvelle cle
          </button>
        }
      />

      {/* Filters */}
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-dark-400 cursor-pointer">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => { setShowInactive(e.target.checked); setPage(1) }}
            className="rounded border-dark-600 bg-dark-700 text-primary-600 focus:ring-primary-500"
          />
          Afficher les cles revoquees
        </label>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Nom</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Prefixe</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Scopes</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Statut</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Derniere utilisation</th>
                <th className="text-center py-3 px-4 text-sm font-medium text-dark-400">Appels</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-dark-400">
                    <Loader2 className="w-5 h-5 animate-spin inline-block mr-2" />
                    Chargement...
                  </td>
                </tr>
              ) : keys.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center">
                    <Key className="w-8 h-8 text-dark-600 mx-auto mb-3" />
                    <p className="text-dark-400">Aucune cle API</p>
                    <button onClick={openCreate} className="text-primary-400 text-sm mt-2 hover:underline">
                      Creer la premiere
                    </button>
                  </td>
                </tr>
              ) : (
                keys.map((key) => (
                  <tr
                    key={key.id}
                    className={cn(
                      'border-b border-dark-700/50 hover:bg-dark-700/30',
                      !key.is_active && 'opacity-50'
                    )}
                  >
                    <td className="py-3 px-4">
                      <span className="text-sm font-medium text-white">{key.name}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm text-dark-400">{key.key_prefix}...</span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1 max-w-xs">
                        {key.scopes.slice(0, 3).map((scope) => (
                          <Badge key={scope} variant="default" size="sm">
                            {scope}
                          </Badge>
                        ))}
                        {key.scopes.length > 3 && (
                          <Badge variant="default" size="sm">
                            +{key.scopes.length - 3}
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {key.is_active ? (
                        <Badge variant="success" size="sm" dot>Active</Badge>
                      ) : (
                        <Badge variant="danger" size="sm" dot>Revoquee</Badge>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm text-dark-400">
                        {key.last_used_at ? formatDate(key.last_used_at) : 'Jamais'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className="text-sm font-mono text-dark-400">
                        {key.usage_count.toLocaleString('fr-FR')}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-1">
                        {key.is_active && (
                          <button
                            onClick={() => setRotateKey(key)}
                            className="p-2 text-dark-400 hover:text-yellow-400 hover:bg-yellow-500/10 rounded-lg transition-colors"
                            title="Rotation de cle"
                          >
                            <RotateCw className="w-4 h-4" />
                          </button>
                        )}
                        {key.is_active && (
                          <button
                            onClick={() => setDeleteKey(key)}
                            className="p-2 text-dark-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                            title="Revoquer"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
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
              {data?.total != null && ` (${data.total} cles)`}
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

      {/* Create Modal */}
      <Modal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Nouvelle cle API"
        description="La cle sera affichee une seule fois apres la creation."
        size="lg"
        footer={
          <ModalFooter
            onCancel={() => setCreateOpen(false)}
            onConfirm={handleCreate}
            confirmText="Creer la cle"
            loading={createMutation.isPending}
          />
        }
      >
        <div className="space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">Nom</label>
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="API Integration ERP"
              className="input w-full"
            />
          </div>

          {/* Scopes */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Permissions ({formScopes.length} selectionnees)
            </label>
            <div className="space-y-3 max-h-60 overflow-y-auto pr-2">
              {AVAILABLE_SCOPES.map(({ group, scopes }) => {
                const allSelected = scopes.every((s) => formScopes.includes(s))
                const someSelected = scopes.some((s) => formScopes.includes(s))
                return (
                  <div key={group} className="bg-dark-700/30 rounded-lg p-3">
                    <label className="flex items-center gap-2 mb-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        ref={(el) => { if (el) el.indeterminate = someSelected && !allSelected }}
                        onChange={() => toggleGroupScopes(scopes)}
                        className="rounded border-dark-600 bg-dark-700 text-primary-600 focus:ring-primary-500"
                      />
                      <span className="text-sm font-medium text-white">{group}</span>
                    </label>
                    <div className="flex flex-wrap gap-2 ml-6">
                      {scopes.map((scope) => (
                        <label
                          key={scope}
                          className={cn(
                            'flex items-center gap-1.5 px-2 py-1 rounded text-xs cursor-pointer transition-colors',
                            formScopes.includes(scope)
                              ? 'bg-primary-600/20 text-primary-300 border border-primary-600/50'
                              : 'bg-dark-700 text-dark-400 border border-dark-600 hover:border-dark-500'
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={formScopes.includes(scope)}
                            onChange={() => toggleScope(scope)}
                            className="sr-only"
                          />
                          {scope}
                        </label>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Rate limit */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Rate limit (requetes/heure)
            </label>
            <input
              type="number"
              value={formRateLimit}
              onChange={(e) => setFormRateLimit(e.target.value)}
              placeholder="1000"
              min={1}
              className="input w-full"
            />
            <p className="text-xs text-dark-500 mt-1">Laisser vide pour la valeur par defaut</p>
          </div>

          {/* Expiration */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">
              Expiration (optionnel)
            </label>
            <input
              type="date"
              value={formExpires}
              onChange={(e) => setFormExpires(e.target.value)}
              className="input w-full"
            />
          </div>
        </div>
      </Modal>

      {/* Key Reveal Modal */}
      <Modal
        isOpen={!!newKey}
        onClose={() => setNewKey(null)}
        title="Cle API creee"
        size="lg"
        closeOnOverlayClick={false}
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-3 bg-yellow-900/20 border border-yellow-700/50 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-yellow-300">
                Copiez cette cle maintenant
              </p>
              <p className="text-xs text-yellow-400/70 mt-1">
                Elle ne sera plus jamais affichee. Conservez-la en lieu sur.
              </p>
            </div>
          </div>

          <div className="relative">
            <div className="flex items-center gap-2 p-3 bg-dark-900 border border-dark-600 rounded-lg font-mono text-sm text-white break-all">
              {newKey?.full_key}
            </div>
            <button
              onClick={() => newKey && copyKey(newKey.full_key)}
              className={cn(
                'absolute top-2 right-2 p-2 rounded-lg transition-colors',
                copied
                  ? 'bg-green-600/20 text-green-400'
                  : 'bg-dark-700 text-dark-400 hover:text-white'
              )}
              title="Copier"
            >
              {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>

          <div className="text-sm text-dark-400">
            <p>Nom : <span className="text-white">{newKey?.name}</span></p>
            <p>Prefixe : <span className="font-mono text-white">{newKey?.key_prefix}</span></p>
          </div>

          <div className="flex justify-end">
            <button
              onClick={() => setNewKey(null)}
              className="btn-primary"
            >
              J'ai copie la cle
            </button>
          </div>
        </div>
      </Modal>

      {/* Delete confirmation */}
      <ConfirmDialog
        isOpen={!!deleteKey}
        onClose={() => setDeleteKey(null)}
        onConfirm={() => deleteKey && deleteMutation.mutate(deleteKey.id)}
        variant="danger"
        title="Revoquer cette cle ?"
        description={`La cle "${deleteKey?.name}" (${deleteKey?.key_prefix}...) sera desactivee. Les applications utilisant cette cle perdront immediatement l'acces.`}
        confirmText="Revoquer"
        loading={deleteMutation.isPending}
      />

      {/* Rotate confirmation */}
      <ConfirmDialog
        isOpen={!!rotateKey}
        onClose={() => setRotateKey(null)}
        onConfirm={() => rotateKey && rotateMutation.mutate(rotateKey.id)}
        variant="warning"
        title="Rotation de cle ?"
        description={`Une nouvelle cle sera generee pour "${rotateKey?.name}". L'ancienne cle sera immediatement revoquee.`}
        confirmText="Generer nouvelle cle"
        loading={rotateMutation.isPending}
      />
    </div>
  )
}
