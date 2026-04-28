import { useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { ArrowLeft, Shield, Briefcase, UserCheck, Eye, Edit, Check, X, ShieldAlert, Activity, Loader2, ToggleLeft, ToggleRight, CheckCircle2 } from 'lucide-react'
import { useUserDetail, useUpdateUser, useUnlockUser, useEntityAuditLogs } from '@/api/queries/useAdmin'
import { normalizeError } from '@shared/errors/normalizer'
import { useHasScope } from '@/hooks/useHasScope'
import { BottomSheet } from '@shared/components/ui/BottomSheet'
import StepUpVerifyModal from '@/components/auth/StepUpVerifyModal'
import type { UserUpdate } from '@/types'
import { cn } from '@/lib/utils'
import { useBrand } from '@/brand/select'

const ROLES = [
  { value: 'staff', label: 'Staff', icon: UserCheck, color: 'border-dark-500 bg-dark-800', iconColor: 'text-dark-300', desc: 'Consulte et opere au quotidien.' },
  { value: 'manager', label: 'Manager', icon: Briefcase, color: 'border-blue-500 bg-blue-500/10', iconColor: 'text-blue-400', desc: 'Gère réservations, stock, clients.' },
  { value: 'admin', label: 'Admin', icon: Shield, color: 'border-purple-500 bg-purple-500/10', iconColor: 'text-purple-400', desc: 'Accès total, configuration, users.' },
] as const

const ROLE_META: Record<string, typeof ROLES[number]> = Object.fromEntries(ROLES.map(r => [r.value, r]))

const isStepUpRequiredMessage = (msg: string) => /step-?up/i.test(msg) || /mfa step-?up/i.test(msg)

export default function AdminUserDetailPage() {
  const brand = useBrand()
  const { id } = useParams({ strict: false }) as { id: string }
  const userId = parseInt(id, 10)

  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState<UserUpdate>({})
  const [saveError, setSaveError] = useState<string | null>(null)
  const [unlockError, setUnlockError] = useState<string | null>(null)
  const [unlockSuccess, setUnlockSuccess] = useState<string | null>(null)
  const [showStepUpModal, setShowStepUpModal] = useState(false)
  const [showRoleSheet, setShowRoleSheet] = useState(false)

  const { data: user, isLoading, error } = useUserDetail(isNaN(userId) ? null : userId)
  const canManageUsers = useHasScope('users:manage')
  const { data: auditData } = useEntityAuditLogs('user', isNaN(userId) ? null : userId, 10)
  const updateMutation = useUpdateUser()
  const unlockMutation = useUnlockUser()

  const startEdit = () => {
    if (!user) return
    setEditForm({ first_name: user.first_name ?? '', last_name: user.last_name ?? '', email: user.email })
    setSaveError(null)
    setIsEditing(true)
  }

  const handleSave = () => {
    setSaveError(null)
    updateMutation.mutate(
      { id: userId, data: editForm },
      {
        onSuccess: () => setIsEditing(false),
        onError: (err) => setSaveError(normalizeError(err).message || 'Erreur'),
      }
    )
  }

  const handleRoleChange = (newRole: string) => {
    updateMutation.mutate(
      { id: userId, data: { role: newRole } },
      { onSuccess: () => setShowRoleSheet(false) }
    )
  }

  const handleToggleActive = () => {
    if (!user) return
    updateMutation.mutate({ id: userId, data: { is_active: !user.is_active } })
  }

  const handleUnlockUser = () => {
    setUnlockError(null)
    setUnlockSuccess(null)
    unlockMutation.mutate(userId, {
      onSuccess: () => setUnlockSuccess('Compte déverrouillé.'),
      onError: (err) => {
        const msg = normalizeError(err).message || 'Erreur'
        if (isStepUpRequiredMessage(msg)) { setShowStepUpModal(true); return }
        setUnlockError(msg)
      },
    })
  }

  // Loading
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-20 bg-dark-800 rounded animate-pulse" />
        <div className="card p-6 flex items-center gap-4 animate-pulse">
          <div className="w-14 h-14 rounded-full bg-dark-800" />
          <div className="space-y-2 flex-1"><div className="h-4 bg-dark-800 rounded w-32" /><div className="h-3 bg-dark-800 rounded w-48" /></div>
        </div>
        {[1, 2, 3].map(i => <div key={i} className="card p-4 h-20 animate-pulse bg-dark-800/50" />)}
      </div>
    )
  }

  if (isNaN(userId) || error || !user) {
    return (
      <div className="card p-8 text-center">
        <p className="text-danger">{error ? normalizeError(error).message : 'Utilisateur introuvable'}</p>
        <Link to="/admin/users" className="btn-secondary mt-4 inline-flex items-center gap-2">
          <ArrowLeft className="w-4 h-4" /> Retour
        </Link>
      </div>
    )
  }

  const initials = ((user.first_name?.[0] ?? '') + (user.last_name?.[0] ?? '')).toUpperCase() || '?'
  const roleMeta = ROLE_META[user.role] || ROLE_META.staff
  const RoleIcon = roleMeta.icon
  const auditLogs = auditData?.items ?? []

  return (
    <div className="space-y-4 pb-8">
      {/* Back */}
      <Link to="/admin/users" className="inline-flex items-center gap-1.5 text-sm text-dark-400 hover:text-dark-200 transition-colors min-h-[44px]">
        <ArrowLeft className="w-4 h-4" />
        Equipe
      </Link>

      {/* Hero */}
      <div className="card p-5">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-lg font-semibold text-white shrink-0">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            {isEditing ? (
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <input className="input text-sm" value={editForm.first_name ?? ''} onChange={e => setEditForm(f => ({ ...f, first_name: e.target.value }))} placeholder="Prénom" />
                  <input className="input text-sm" value={editForm.last_name ?? ''} onChange={e => setEditForm(f => ({ ...f, last_name: e.target.value }))} placeholder="Nom" />
                </div>
                <input className="input text-sm" type="email" value={editForm.email ?? ''} onChange={e => setEditForm(f => ({ ...f, email: e.target.value }))} placeholder="Email" />
                {saveError && <p className="text-xs text-danger">{saveError}</p>}
                <div className="flex gap-2">
                  <button onClick={handleSave} disabled={updateMutation.isPending} className="btn-primary btn-sm flex items-center gap-1">
                    {updateMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                    Enregistrer
                  </button>
                  <button onClick={() => setIsEditing(false)} className="btn-secondary btn-sm flex items-center gap-1">
                    <X className="w-3 h-3" /> Annuler
                  </button>
                </div>
              </div>
            ) : (
              <>
                <p className="font-semibold">{user.first_name} {user.last_name}</p>
                <p className="text-sm text-dark-400">{user.email}</p>
                {user.created_at && (
                  <p className="text-xs text-dark-500 mt-1">
                    Membre depuis {new Date(user.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}
                  </p>
                )}
              </>
            )}
          </div>
          {!isEditing && canManageUsers && (
            <button onClick={startEdit} className="p-2 hover:bg-[var(--s2)] rounded-lg transition-colors shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center" aria-label="Modifier">
              <Edit className="w-4 h-4 text-dark-400" />
            </button>
          )}
        </div>
      </div>

      {/* Role */}
      <div className="card p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center', roleMeta.color.split(' ')[1])}>
              <RoleIcon className={cn('w-5 h-5', roleMeta.iconColor)} />
            </div>
            <div>
              <p className="text-sm font-medium">{roleMeta.label}</p>
              <p className="text-xs text-dark-400">{roleMeta.desc}</p>
            </div>
          </div>
          {canManageUsers && (
            <button
              onClick={() => setShowRoleSheet(true)}
              className="text-xs text-primary-400 hover:text-primary-300 active:text-primary-200 font-medium min-h-[44px] min-w-[44px] px-3 cursor-pointer"
            >
              Changer
            </button>
          )}
        </div>
      </div>

      {/* Statut */}
      <div className="card p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center', user.is_active ? 'bg-green-500/10' : 'bg-red-500/10')}>
              {user.is_active ? <ToggleRight className="w-5 h-5 text-green-400" /> : <ToggleLeft className="w-5 h-5 text-red-400" />}
            </div>
            <div>
              <p className="text-sm font-medium">{user.is_active ? 'Compte actif' : 'Compte desactive'}</p>
              <p className="text-xs text-dark-400">{user.is_active ? `Peut se connecter et utiliser ${brand.name}` : 'Accès bloqué à toutes les fonctionnalités'}</p>
            </div>
          </div>
          {canManageUsers && (
            <button
              onClick={handleToggleActive}
              disabled={updateMutation.isPending}
              className={cn(
                'text-xs font-medium min-h-[44px] px-3',
                user.is_active ? 'text-red-400 hover:text-red-300' : 'text-green-400 hover:text-green-300'
              )}
            >
              {user.is_active ? 'Desactiver' : 'Reactiver'}
            </button>
          )}
        </div>
      </div>

      {/* Actions admin */}
      {canManageUsers && (
        <div className="card p-4 space-y-3">
          <p className="text-xs text-dark-500 font-medium uppercase tracking-wide">Actions</p>
          <button
            onClick={handleUnlockUser}
            disabled={unlockMutation.isPending}
            className="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-[var(--s2)] transition-colors min-h-[44px]"
          >
            <ShieldAlert className="w-5 h-5 text-amber-400" />
            <div className="text-left flex-1">
              <p className="text-sm font-medium">Deverrouiller le compte</p>
              <p className="text-xs text-dark-400">Si bloque apres trop de tentatives</p>
            </div>
            {unlockMutation.isPending && <Loader2 className="w-4 h-4 animate-spin text-dark-400" />}
          </button>
          {unlockSuccess && <p className="text-xs text-green-400 px-3">{unlockSuccess}</p>}
          {unlockError && <p className="text-xs text-red-400 px-3">{unlockError}</p>}
        </div>
      )}

      {/* Activite recente */}
      {auditLogs.length > 0 && (
        <div className="card p-4 space-y-3">
          <p className="text-xs text-dark-500 font-medium uppercase tracking-wide flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5" />
            Activite recente
          </p>
          <div className="space-y-2">
            {auditLogs.slice(0, 8).map((log) => (
              <div key={log.id} className="flex items-start gap-3 py-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-dark-500 mt-2 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-dark-300 truncate">{log.action}</p>
                  <p className="text-[10px] text-dark-500">
                    {new Date(log.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bottom sheet changement role */}
      <BottomSheet isOpen={showRoleSheet} onClose={() => setShowRoleSheet(false)} title="Changer le role">
        <div className="px-6 pb-6 space-y-3">
          {ROLES.map((r) => {
            const active = user.role === r.value
            return (
              <button
                key={r.value}
                type="button"
                onClick={() => handleRoleChange(r.value)}
                disabled={updateMutation.isPending}
                className={cn(
                  'w-full flex items-start gap-3 p-4 rounded-xl border-2 text-left transition-all active:scale-[0.98] min-h-[44px] cursor-pointer',
                  active ? r.color : 'border-dark-700 bg-dark-900/40'
                )}
                style={{ touchAction: 'manipulation' }}
              >
                <r.icon className={cn('w-5 h-5 mt-0.5 shrink-0', active ? r.iconColor : 'text-dark-400')} />
                <div className="flex-1">
                  <p className={cn('text-sm font-semibold', active ? 'text-white' : 'text-dark-300')}>{r.label}</p>
                  <p className="text-xs text-dark-400 mt-0.5">{r.desc}</p>
                </div>
                {active && <CheckCircle2 className={cn('w-5 h-5 shrink-0 mt-0.5', r.iconColor)} />}
              </button>
            )
          })}
        </div>
      </BottomSheet>

      {/* Step-up MFA modal */}
      {showStepUpModal && (
        <StepUpVerifyModal
          isOpen
          onClose={() => setShowStepUpModal(false)}
          onVerified={() => { setShowStepUpModal(false); handleUnlockUser() }}
        />
      )}
    </div>
  )
}
