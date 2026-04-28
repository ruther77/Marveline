import { useState, useMemo } from 'react'
import {
  useFeatureFlags,
  useToggleFeatureFlag,
  useCreateFeatureFlag,
  useUpdateFeatureFlag,
  useDeleteFeatureFlag,
} from '@/api/queries'
import type { FeatureFlagList, FeatureFlagCreate } from '@/types/featureFlag'
import { normalizeError } from '@shared/errors/normalizer'
import { ErrorState } from '@shared/components/ui/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { ActionError } from '@shared/components/ui/ActionError'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { DeleteConfirm } from '@shared/components/ui/ConfirmDialog'
import { cn } from '@/lib/utils'
import {
  ToggleLeft,
  Plus,
  Pencil,
  Trash2,
  Flag,
  Percent,
  Info,
  Zap,
  Search,
  Loader2,
} from 'lucide-react'

// ── Catalogue métier des flags connus ────────────────────────────────────────

const FLAG_CATALOG: Record<string, { label: string; description: string; module: string }> = {
  enable_loyalty: { label: 'Programme fidélité', description: 'Points, récompenses et suivi fidélité client', module: 'Fidélité' },
  enable_deposits: { label: 'Gestion des cautions', description: 'Saisie et suivi des cautions sur les réservations', module: 'Facturation' },
  enable_credit_notes: { label: 'Avoirs', description: 'Création d\'avoirs sur les factures', module: 'Facturation' },
  enable_delivery_zones: { label: 'Zones de livraison', description: 'Calcul automatique des frais par zone', module: 'Logistique' },
  enable_stock_items: { label: 'Suivi unitaire du stock', description: 'Suivi individuel des articles (code-barres, état)', module: 'Inventaire' },
  enable_damage_tracking: { label: 'Suivi des dommages', description: 'Déclaration et suivi des dommages articles', module: 'Inventaire' },
  enable_supplier_orders: { label: 'Commandes fournisseurs', description: 'Commandes et réceptions fournisseurs', module: 'Approvisionnement' },
  enable_devis_signature: { label: 'Signature des devis', description: 'Signature électronique des devis par le client', module: 'Devis' },
  enable_relances: { label: 'Relances automatiques', description: 'Envoi automatique de relances factures en retard', module: 'Facturation' },
  enable_restaurant: { label: 'Module restaurant', description: 'Accès à l\'application restaurant', module: 'Restaurant' },
  enable_epicerie: { label: 'Module épicerie', description: 'Accès à l\'application épicerie', module: 'Épicerie' },
}

function getFlagInfo(name: string) {
  return FLAG_CATALOG[name] ?? null
}

const MODULE_COLORS: Record<string, string> = {
  'Facturation': 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  'Logistique': 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  'Inventaire': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  'Approvisionnement': 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  'Devis': 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  'Fidélité': 'bg-pink-500/10 text-pink-400 border-pink-500/20',
  'Restaurant': 'bg-red-500/10 text-red-400 border-red-500/20',
  'Épicerie': 'bg-lime-500/10 text-lime-400 border-lime-500/20',
}

// ── Toggle switch ────────────────────────────────────────────────────────────

function ToggleSwitch({ enabled, onToggle, disabled, loading }: {
  enabled: boolean; onToggle: () => void; disabled?: boolean; loading?: boolean
}) {
  return (
    <button
      onClick={onToggle}
      disabled={disabled || loading}
      className={cn(
        'relative inline-flex h-7 w-12 items-center rounded-full transition-colors min-w-[48px] shrink-0',
        enabled ? 'bg-green-600' : 'bg-dark-500',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      {loading ? (
        <Loader2 className="w-4 h-4 text-white animate-spin mx-auto" />
      ) : (
        <span
          className={cn(
            'inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform',
            enabled ? 'translate-x-6' : 'translate-x-1',
          )}
        />
      )}
    </button>
  )
}

// ── Rollout bar (visual) ─────────────────────────────────────────────────────

function RolloutBar({ pct, enabled }: { pct: number; enabled: boolean }) {
  if (!enabled) return null
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-dark-900 rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all',
            pct === 100 ? 'bg-green-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-400',
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] text-dark-400 tabular-nums w-8 text-right">{pct}%</span>
    </div>
  )
}

// ── Flag card ────────────────────────────────────────────────────────────────

function FlagCard({
  flag,
  onToggle,
  onEdit,
  onDelete,
  toggling,
}: {
  flag: FeatureFlagList
  onToggle: () => void
  onEdit: () => void
  onDelete: () => void
  toggling: boolean
}) {
  const info = getFlagInfo(flag.name)
  const moduleName = info?.module || 'Custom'
  const moduleColor = MODULE_COLORS[moduleName] || 'bg-dark-100/10 text-dark-400 border-dark-200/20'

  return (
    <div className={cn(
      'card p-4 hover:shadow-md transition-all',
      !flag.is_enabled && 'opacity-60',
    )}>
      {/* Row 1 : Label + Module badge + Toggle */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold">{info?.label || flag.name}</h3>
            <span className={cn('text-[10px] px-1.5 py-0.5 rounded-full border font-medium', moduleColor)}>
              {moduleName}
            </span>
          </div>
          <p className="text-xs text-dark-400 mt-1 line-clamp-1">
            {info?.description || flag.description || 'Aucune description'}
          </p>
        </div>
        <ToggleSwitch enabled={flag.is_enabled} onToggle={onToggle} loading={toggling} />
      </div>

      {/* Row 2 : Rollout bar + technical name + actions */}
      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <code className="text-[11px] text-dark-500 font-mono truncate">{flag.name}</code>
          {flag.is_enabled && (
            <span className="text-[11px] text-dark-400 shrink-0">
              {flag.rollout_pct === 100 ? 'Tout le monde' : `${flag.rollout_pct}% des utilisateurs`}
            </span>
          )}
        </div>
        <div className="flex items-center gap-0.5 shrink-0">
          <button
            onClick={onEdit}
            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-dark-50 hover:bg-dark-700/30 rounded-lg transition-colors"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onDelete}
            className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-dark-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Rollout bar */}
      {flag.is_enabled && flag.rollout_pct < 100 && (
        <div className="mt-2">
          <RolloutBar pct={flag.rollout_pct} enabled={flag.is_enabled} />
        </div>
      )}
    </div>
  )
}

function FlagCardSkeleton() {
  return (
    <div className="card p-4 animate-pulse space-y-3">
      <div className="flex items-start justify-between">
        <div className="space-y-2 flex-1">
          <div className="flex gap-2">
            <div className="h-4 bg-dark-100/10 rounded w-32" />
            <div className="h-4 bg-dark-100/10 rounded-full w-16" />
          </div>
          <div className="h-3 bg-dark-100/10 rounded w-56" />
        </div>
        <div className="w-12 h-7 bg-dark-100/10 rounded-full shrink-0" />
      </div>
      <div className="h-3 bg-dark-100/10 rounded w-40" />
    </div>
  )
}

// ── Page principale ──────────────────────────────────────────────────────────

export default function FeatureFlagsPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const [editingFlag, setEditingFlag] = useState<FeatureFlagList | null>(null)
  const [deleteFlag, setDeleteFlag] = useState<FeatureFlagList | null>(null)
  const [search, setSearch] = useState('')

  const [formName, setFormName] = useState('')
  const [isCustom, setIsCustom] = useState(false)
  const [formDesc, setFormDesc] = useState('')
  const [formEnabled, setFormEnabled] = useState(false)
  const [formRollout, setFormRollout] = useState(100)

  const { data, isLoading, error: queryError, refetch } = useFeatureFlags({ skip: 0, limit: 200 })
  const flags = data?.items || []

  const toggleMutation = useToggleFeatureFlag()
  const createMutation = useCreateFeatureFlag()
  const updateMutation = useUpdateFeatureFlag()
  const deleteMutation = useDeleteFeatureFlag()

  // Filtrage par recherche
  const filtered = useMemo(() => {
    if (!search.trim()) return flags
    const q = search.toLowerCase()
    return flags.filter((f) => {
      const info = getFlagInfo(f.name)
      return f.name.includes(q)
        || (info?.label.toLowerCase().includes(q))
        || (info?.module.toLowerCase().includes(q))
        || (f.description?.toLowerCase().includes(q))
    })
  }, [flags, search])

  // Groupement par module
  const grouped = useMemo(() => {
    const groups: Record<string, FeatureFlagList[]> = {}
    for (const f of filtered) {
      const mod = getFlagInfo(f.name)?.module || 'Autre'
      if (!groups[mod]) groups[mod] = []
      groups[mod].push(f)
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
  }, [filtered])

  const activeCount = flags.filter((f) => f.is_enabled).length

  const openCreate = () => {
    setEditingFlag(null)
    setFormName('')
    setFormDesc('')
    setFormEnabled(false)
    setFormRollout(100)
    setIsCustom(false)
    setModalOpen(true)
  }

  const openEdit = (flag: FeatureFlagList) => {
    setEditingFlag(flag)
    setFormName(flag.name)
    setFormDesc(flag.description || '')
    setFormEnabled(flag.is_enabled)
    setFormRollout(flag.rollout_pct)
    setModalOpen(true)
  }

  const closeModal = () => {
    setModalOpen(false)
    setEditingFlag(null)
  }

  const handleSubmit = () => {
    if (editingFlag) {
      updateMutation.mutate({
        id: editingFlag.id,
        data: {
          description: formDesc || undefined,
          is_enabled: formEnabled,
          rollout_pct: formRollout,
        },
      }, { onSuccess: closeModal })
    } else {
      createMutation.mutate({
        name: formName,
        description: formDesc || undefined,
        is_enabled: formEnabled,
        rollout_pct: formRollout,
      } as FeatureFlagCreate, { onSuccess: closeModal })
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  const rolloutLabel = formRollout === 0
    ? 'Personne'
    : formRollout === 100
      ? 'Tout le monde'
      : `${formRollout}% des utilisateurs`

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <PageHeader title="Fonctionnalités" subtitle="Activer ou désactiver les modules" />
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Nouvelle</span>
        </button>
      </div>

      {/* KPI strip */}
      {!isLoading && flags.length > 0 && (
        <div className="flex items-center gap-4">
          <div className="card px-4 py-2">
            <div className="text-[11px] text-dark-500">Total</div>
            <div className="text-sm font-bold">{flags.length}</div>
          </div>
          <div className="card px-4 py-2">
            <div className="text-[11px] text-dark-500">Actives</div>
            <div className="text-sm font-bold text-green-400">{activeCount}</div>
          </div>
          <div className="card px-4 py-2">
            <div className="text-[11px] text-dark-500">Inactives</div>
            <div className="text-sm font-bold text-dark-400">{flags.length - activeCount}</div>
          </div>
        </div>
      )}

      {/* Search */}
      {flags.length > 5 && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher une fonctionnalité..."
            className="input w-full pl-10 py-2.5 text-sm rounded-xl"
          />
        </div>
      )}

      {/* Liste groupée */}
      {queryError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <FlagCardSkeleton key={i} />)}
        </div>
      ) : flags.length === 0 ? (
        <div className="card py-12 text-center">
          <Flag className="w-8 h-8 text-dark-500 mx-auto mb-4" />
          <p className="text-dark-400">Aucune fonctionnalité configurée</p>
          <button onClick={openCreate} className="text-primary-400 text-sm mt-2 hover:underline">
            Ajouter la première
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="card py-8 text-center">
          <p className="text-dark-400 text-sm">Aucun résultat pour "{search}"</p>
          <button onClick={() => setSearch('')} className="text-primary-400 text-xs mt-2 hover:underline">Effacer</button>
        </div>
      ) : (
        <div className="space-y-6">
          {grouped.map(([module, moduleFlags]) => (
            <div key={module}>
              <h3 className="text-xs font-semibold text-dark-400 uppercase tracking-wider mb-2 px-1">{module}</h3>
              <div className="space-y-2">
                {moduleFlags.map((flag) => (
                  <FlagCard
                    key={flag.id}
                    flag={flag}
                    onToggle={() => toggleMutation.mutate({ id: flag.id, is_enabled: !flag.is_enabled })}
                    onEdit={() => openEdit(flag)}
                    onDelete={() => setDeleteFlag(flag)}
                    toggling={toggleMutation.isPending}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-blue-500/5 border border-blue-500/10">
        <Info className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
        <div className="text-xs text-dark-400">
          <p className="font-medium text-dark-300 mb-1">Déploiement progressif</p>
          <p>Chaque fonctionnalité peut être activée pour un pourcentage d'utilisateurs. Utile pour tester avant un lancement complet.</p>
        </div>
      </div>

      {/* Modal création/édition */}
      <Modal
        isOpen={modalOpen}
        onClose={closeModal}
        title={editingFlag ? 'Modifier la fonctionnalité' : 'Nouvelle fonctionnalité'}
        footer={
          <ModalFooter
            onCancel={closeModal}
            onConfirm={handleSubmit}
            confirmText={editingFlag ? 'Enregistrer' : 'Créer'}
            loading={isSaving}
          />
        }
      >
        <div className="space-y-5">
          <ActionError
            message={(createMutation.error || updateMutation.error) ? (normalizeError(createMutation.error || updateMutation.error).message || 'Une erreur est survenue') : null}
            onDismiss={() => { createMutation.reset(); updateMutation.reset() }}
          />

          {/* Sélection fonctionnalité */}
          {!editingFlag ? (
            <div>
              <label className="block text-sm font-medium mb-1.5">Fonctionnalité</label>
              {!isCustom ? (
                <select
                  value={formName}
                  onChange={(e) => {
                    const key = e.target.value
                    if (key === '__custom') {
                      setIsCustom(true)
                      setFormName('')
                      setFormDesc('')
                    } else {
                      setFormName(key)
                      const info = getFlagInfo(key)
                      if (info) setFormDesc(info.description)
                    }
                  }}
                  className="input w-full text-sm"
                >
                  <option value="">— Choisir une fonctionnalité —</option>
                  {Object.entries(FLAG_CATALOG)
                    .filter(([key]) => !flags.some((f) => f.name === key))
                    .map(([key, info]) => (
                      <option key={key} value={key}>
                        {info.label} ({info.module})
                      </option>
                    ))}
                  <option value="__custom">Personnalisée...</option>
                </select>
              ) : (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                    placeholder="enable_mon_module"
                    className="input w-full font-mono text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => { setIsCustom(false); setFormName(''); setFormDesc('') }}
                    className="text-xs text-primary-400 hover:underline"
                  >
                    Revenir au catalogue
                  </button>
                </div>
              )}
              {formName && !isCustom && (
                <p className="text-xs text-dark-400 mt-2">
                  {getFlagInfo(formName)?.description || formDesc}
                </p>
              )}
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium mb-1.5">Fonctionnalité</label>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">{getFlagInfo(editingFlag.name)?.label || editingFlag.name}</span>
                <code className="text-[11px] text-dark-500 font-mono">{editingFlag.name}</code>
              </div>
            </div>
          )}

          {/* Description (éditable uniquement pour custom) */}
          {(isCustom || (editingFlag && !getFlagInfo(editingFlag.name))) && (
            <div>
              <label className="block text-sm font-medium mb-1.5">Description</label>
              <input
                type="text"
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
                placeholder="Décrivez ce que cette fonctionnalité contrôle"
                className="input w-full text-sm"
              />
            </div>
          )}

          {/* Toggle activé */}
          <div className="flex items-center justify-between py-3 px-4 rounded-xl bg-dark-900/50">
            <div>
              <p className="text-sm font-medium">Activée</p>
              <p className="text-[11px] text-dark-500">Effet immédiat sur tous les utilisateurs concernés</p>
            </div>
            <ToggleSwitch enabled={formEnabled} onToggle={() => setFormEnabled(!formEnabled)} />
          </div>

          {/* Déploiement progressif */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium">Déploiement</label>
              <span className={cn(
                'text-xs font-medium px-2 py-0.5 rounded-full',
                formRollout === 100 ? 'bg-green-500/10 text-green-400' :
                formRollout === 0 ? 'bg-red-500/10 text-red-400' :
                'bg-amber-500/10 text-amber-400',
              )}>
                {rolloutLabel}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={formRollout}
              onChange={(e) => setFormRollout(Number(e.target.value))}
              className="w-full accent-primary-500 h-2"
            />
            <div className="flex justify-between text-[10px] text-dark-500 mt-1 px-0.5">
              <span>0%</span>
              <span>25%</span>
              <span>50%</span>
              <span>75%</span>
              <span>100%</span>
            </div>
          </div>
        </div>
      </Modal>

      {/* Confirmation suppression */}
      <DeleteConfirm
        isOpen={!!deleteFlag}
        onClose={() => setDeleteFlag(null)}
        onConfirm={() => deleteFlag && deleteMutation.mutate(deleteFlag.id, { onSuccess: () => setDeleteFlag(null) })}
        itemName={getFlagInfo(deleteFlag?.name || '')?.label || deleteFlag?.name}
        loading={deleteMutation.isPending}
      />
    </div>
  )
}
