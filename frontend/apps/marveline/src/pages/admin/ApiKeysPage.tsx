import { useState } from 'react'
import { useApiKeysList, useCreateApiKey, useDeleteApiKey, useRotateApiKey } from '@/api/queries'
import type { ApiKeyList, ApiKeyCreate, ApiKeyCreated } from '@/types/apiKey'
import { PageHeader } from '@shared/components/ui/Breadcrumb'
import { ActionError, ErrorState } from '@shared/components/ui'
import { Badge } from '@shared/components/ui/Badge'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { ConfirmDialog } from '@shared/components/ui/ConfirmDialog'
import { formatDate } from '@/lib/utils'
import { cn } from '@/lib/utils'
import {
  Key,
  Plus,
  Trash2,
  RotateCw,
  Copy,
  Check,
  Eye,
  EyeOff,
  AlertTriangle,
} from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'

const AVAILABLE_SCOPES = [
  { group: 'Produits', scopes: ['products:read', 'products:write', 'products:delete'] },
  { group: 'Catégories', scopes: ['categories:read', 'categories:write', 'categories:delete'] },
  { group: 'Formules', scopes: ['bundles:read', 'bundles:write', 'bundles:delete'] },
  { group: 'Reservations', scopes: ['reservations:read', 'reservations:write', 'reservations:delete'] },
  { group: 'Factures', scopes: ['invoices:read', 'invoices:write'] },
  { group: 'Clients', scopes: ['customers:read', 'customers:write', 'customers:delete'] },
  { group: 'Inventaire', scopes: ['inventory:read', 'inventory:write'] },
  { group: 'Utilisateurs', scopes: ['users:read', 'users:write', 'users:admin'] },
  { group: 'Audit', scopes: ['audit:read'] },
]

export default function ApiKeysPage() {
  const [page, setPage] = useState(1)
  const [showInactive, setShowInactive] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteKey, setDeleteKey] = useState<ApiKeyList | null>(null)
  const [rotateKey, setRotateKey] = useState<ApiKeyList | null>(null)
  const [newKey, setNewKey] = useState<ApiKeyCreated | null>(null)
  const [copied, setCopied] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  // Create form state
  const [formName, setFormName] = useState('')
  const [formScopes, setFormScopes] = useState<string[]>([])
  const [formRateLimit, setFormRateLimit] = useState('1000')
  const [formExpires, setFormExpires] = useState('')

  const { data, isLoading, error: queryError, refetch } = useApiKeysList({ skip: (page - 1) * 50, limit: 50, include_inactive: showInactive })

  const keys = data?.items || []
  const totalPages = Math.ceil((data?.total ?? 0) / 50) || 1

  const createMutation = useCreateApiKey()
  const deleteMutation = useDeleteApiKey()
  const rotateMutation = useRotateApiKey()

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
    } as ApiKeyCreate, {
      onSuccess: (created) => { setCreateOpen(false); setNewKey(created as ApiKeyCreated) },
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
        subtitle="Clés d'accès machine-to-machine (M2M)"
        breadcrumbs={[{ label: 'Admin' }, { label: 'API Keys' }]}
        actions={
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Nouvelle cle</span>
          </button>
        }
      />

      {/* Filters */}
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-dark-400 cursor-pointer">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => { setShowInactive(e.target.checked); setPage(1) }}
            className="rounded border-dark-600 bg-dark-900 text-primary-600 focus:ring-primary-500"
          />
          Afficher les cles révoquées
        </label>
      </div>

      <ActionError message={actionError} onDismiss={() => setActionError(null)} />

      {queryError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : (
      /* Liste */
      <div className="card p-0 overflow-hidden">
        {/* Vue mobile */}
        <div className="sm:hidden">
          {isLoading ? (
            <div className="animate-pulse divide-y divide-dark-600">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 px-4 py-4">
                  <div className="flex-1 space-y-2">
                    <div className="h-3 skel rounded w-36" />
                    <div className="h-2 skel rounded w-52" />
                  </div>
                  <div className="h-5 skel rounded w-14 shrink-0" />
                </div>
              ))}
            </div>
          ) : keys.length === 0 ? (
            <div className="py-12 text-center space-y-4">
              <Key className="w-8 h-8 text-dark-600 mx-auto" />
              <p className="text-dark-400">Aucune clé API créée.</p>
              <button onClick={openCreate} className="btn-primary text-sm">
                Créer la première clé
              </button>
            </div>
          ) : (
            keys.map((key) => (
              <div
                key={key.id}
                className={cn(
                  'px-4 py-4 border-b border-dark-600 last:border-0',
                  !key.is_active && 'opacity-50'
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium">{key.name}</span>
                      {key.is_active ? (
                        <Badge variant="success" size="sm" dot>Active</Badge>
                      ) : (
                        <Badge variant="danger" size="sm" dot>Révoquée</Badge>
                      )}
                    </div>
                    <div className="text-xs text-dark-400 mt-0.5 font-mono">{key.key_prefix}...</div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {key.scopes.slice(0, 2).map((scope) => (
                        <Badge key={scope} variant="default" size="sm">{scope}</Badge>
                      ))}
                      {key.scopes.length > 2 && (
                        <Badge variant="default" size="sm">+{key.scopes.length - 2}</Badge>
                      )}
                    </div>
                    <div className="text-xs text-dark-500 mt-1">
                      {key.last_used_at ? formatDate(key.last_used_at) : 'Jamais utilisée'}
                      {' · '}
                      {key.usage_count.toLocaleString('fr-FR')} appels
                    </div>
                  </div>
                  {key.is_active && (
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => setRotateKey(key)}
                        className="p-1.5 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-yellow-400 hover:bg-yellow-500/10 rounded-lg transition-colors"
                        title="Rotation"
                        aria-label="Rotation de clé"
                      >
                        <RotateCw className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setDeleteKey(key)}
                        className="p-1.5 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                        title="Revoquer"
                        aria-label="Révoquer la clé"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Vue desktop */}
        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-600">
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">Nom</th>
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">Prefixe</th>
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">Scopes</th>
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">Statut</th>
                <th className="text-left py-4 px-4 text-sm font-medium text-dark-400">Dernière utilisation</th>
                <th className="text-center py-4 px-4 text-sm font-medium text-dark-400">Appels</th>
                <th className="text-right py-4 px-4 text-sm font-medium text-dark-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="border-b border-dark-600 animate-pulse">
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-28" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-40" /></td>
                    <td className="py-4 px-4"><div className="h-5 bg-dark-900 rounded w-20" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-24" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-24" /></td>
                    <td className="py-4 px-4"><div className="h-3 bg-dark-900 rounded w-16" /></td>
                    <td className="py-4 px-4"><div className="h-6 bg-dark-900 rounded w-6 ml-auto" /></td>
                  </tr>
                ))
              ) : keys.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center">
                    <div className="space-y-4">
                      <Key className="w-8 h-8 text-dark-600 mx-auto" />
                      <p className="text-dark-400">Aucune clé API créée.</p>
                      <button onClick={openCreate} className="btn-primary text-sm">
                        Créer la première clé
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                keys.map((key) => (
                  <tr
                    key={key.id}
                    className={cn(
                      'border-b border-dark-600/50 hover:bg-dark-600/30',
                      !key.is_active && 'opacity-50'
                    )}
                  >
                    <td className="py-4 px-4">
                      <span className="text-sm font-medium">{key.name}</span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="font-mono text-sm text-dark-400">{key.key_prefix}...</span>
                    </td>
                    <td className="py-4 px-4">
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
                    <td className="py-4 px-4">
                      {key.is_active ? (
                        <Badge variant="success" size="sm" dot>Active</Badge>
                      ) : (
                        <Badge variant="danger" size="sm" dot>Révoquée</Badge>
                      )}
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-sm text-dark-400">
                        {key.last_used_at ? formatDate(key.last_used_at) : 'Jamais'}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-center">
                      <span className="text-sm font-mono text-dark-400">
                        {key.usage_count.toLocaleString('fr-FR')}
                      </span>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center justify-end gap-1">
                        {key.is_active && (
                          <button
                            onClick={() => setRotateKey(key)}
                            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-yellow-400 hover:bg-yellow-500/10 rounded-lg transition-colors"
                            title="Rotation de clé"
                            aria-label="Rotation de clé"
                          >
                            <RotateCw className="w-4 h-4" />
                          </button>
                        )}
                        {key.is_active && (
                          <button
                            onClick={() => setDeleteKey(key)}
                            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                            title="Révoquer"
                            aria-label="Révoquer la clé"
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
          <div className="flex items-center justify-between px-4 py-4 border-t border-dark-600">
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
      )}

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
            confirmText="Créer la clé"
            loading={createMutation.isPending}
          />
        }
      >
        <div className="space-y-4">
          <ActionError
            message={createMutation.error ? (normalizeError(createMutation.error).message || 'Une erreur est survenue') : null}
            onDismiss={() => createMutation.reset()}
          />
          {/* Name */}
          <div>
            <label className="block text-sm text-dark-400 mb-1">Nom</label>
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="API Integration ERP"
              className="input"
            />
          </div>

          {/* Scopes */}
          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Permissions ({formScopes.length} selectionnees)
            </label>
            <div className="space-y-4 max-h-60 overflow-y-auto pr-2">
              {AVAILABLE_SCOPES.map(({ group, scopes }) => {
                const allSelected = scopes.every((s) => formScopes.includes(s))
                const someSelected = scopes.some((s) => formScopes.includes(s))
                return (
                  <div key={group} className="bg-dark-900/30 rounded-lg p-4">
                    <label className="flex items-center gap-2 mb-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        ref={(el) => { if (el) el.indeterminate = someSelected && !allSelected }}
                        onChange={() => toggleGroupScopes(scopes)}
                        className="rounded border-dark-600 bg-dark-900 text-primary-600 focus:ring-primary-500"
                      />
                      <span className="text-sm font-medium">{group}</span>
                    </label>
                    <div className="flex flex-wrap gap-2 ml-6">
                      {scopes.map((scope) => (
                        <label
                          key={scope}
                          className={cn(
                            'flex items-center gap-1.5 px-2 py-1 rounded text-xs cursor-pointer transition-colors',
                            formScopes.includes(scope)
                              ? 'bg-primary-600/20 text-primary-300 border border-primary-600/50'
                              : 'btn-ghost'
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
            <label className="block text-sm text-dark-400 mb-1">
              Rate limit (requetes/heure)
            </label>
            <input
              type="number"
              value={formRateLimit}
              onChange={(e) => setFormRateLimit(e.target.value)}
              placeholder="1000"
              min={1}
              className="input"
            />
            <p className="text-xs text-dark-500 mt-1">Laisser vide pour la valeur par defaut</p>
          </div>

          {/* Expiration */}
          <div>
            <label className="block text-sm text-dark-400 mb-1">
              Expiration (optionnel)
            </label>
            <input
              type="date"
              value={formExpires}
              onChange={(e) => setFormExpires(e.target.value)}
              className="input"
            />
          </div>
        </div>
      </Modal>

      {/* Key Reveal Modal */}
      <Modal
        isOpen={!!newKey}
        onClose={() => setNewKey(null)}
        title="Clé API créée"
        size="lg"
        closeOnOverlayClick={false}
      >
        <div className="space-y-4">
          <div className="flex items-start gap-4 p-4 bg-yellow-900/20 border border-yellow-700/50 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-yellow-300">
                Copiez cette clé maintenant
              </p>
              <p className="text-xs text-yellow-400/70 mt-1">
                Elle ne sera plus jamais affichee. Conservez-la en lieu sur.
              </p>
            </div>
          </div>

          <div className="relative">
            <div className="flex items-center gap-2 p-4 card font-mono text-sm break-all">
              {newKey?.full_key}
            </div>
            <button
              onClick={() => newKey && copyKey(newKey.full_key)}
              className={cn(
                'absolute top-2 right-2 p-2 rounded-lg transition-colors',
                copied
                  ? 'bg-green-600/20 text-green-400'
                  : 'btn-ghost'
              )}
              title="Copier la clé"
              aria-label="Copier la clé"
            >
              {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>

          <div className="text-sm text-dark-400">
            <p>Nom : <span className="">{newKey?.name}</span></p>
            <p>Prefixe : <span className="font-mono">{newKey?.key_prefix}</span></p>
          </div>

          <div className="flex justify-end">
            <button
              onClick={() => setNewKey(null)}
              className="btn-primary"
            >
              J'ai copie la clé
            </button>
          </div>
        </div>
      </Modal>

      {/* Delete confirmation */}
      <ConfirmDialog
        isOpen={!!deleteKey}
        onClose={() => setDeleteKey(null)}
        onConfirm={() => deleteKey && deleteMutation.mutate(deleteKey.id, { onSuccess: () => { setActionError(null); setDeleteKey(null) }, onError: (err) => { setDeleteKey(null); setActionError(normalizeError(err).message || 'Erreur lors de la révocation') } })}
        variant="danger"
        title="Revoquer cette clé ?"
        description={`La cle "${deleteKey?.name}" (${deleteKey?.key_prefix}...) sera desactivee. Les applications utilisant cette clé perdront immediatement l'acces.`}
        confirmText="Revoquer"
        loading={deleteMutation.isPending}
      />

      {/* Rotate confirmation */}
      <ConfirmDialog
        isOpen={!!rotateKey}
        onClose={() => setRotateKey(null)}
        onConfirm={() => rotateKey && rotateMutation.mutate(rotateKey.id, { onSuccess: (created) => { setActionError(null); setRotateKey(null); setNewKey(created as ApiKeyCreated) }, onError: (err) => { setRotateKey(null); setActionError(normalizeError(err).message || 'Erreur lors de la rotation de la clé') } })}
        variant="warning"
        title="Rotation de cle ?"
        description={`Une nouvelle clé sera générée pour "${rotateKey?.name}". L'ancienne cle sera immediatement révoquée.`}
        confirmText="Generer nouvelle clé"
        loading={rotateMutation.isPending}
      />
    </div>
  )
}
