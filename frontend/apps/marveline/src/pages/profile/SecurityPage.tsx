import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/authStore'
import { useChangePassword, useMfaStatus } from '@/api/queries/useAuth'
import { useWebAuthnCredentials, useRegisterWebAuthn, useDeleteWebAuthnCredential } from '@/api/queries/useWebAuthn'
import {
  Loader2,
  Eye,
  EyeOff,
  Check,
  X,
  Shield,
  ShieldAlert,
  Key,
  Monitor,
  Fingerprint,
  Plus,
  Trash2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { normalizeError } from '@shared/errors/normalizer'

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Mot de passe actuel requis'),
    new_password: z
      .string()
      .min(12, 'Minimum 12 caractères')
      .regex(/[A-Z]/, 'Au moins une majuscule')
      .regex(/[a-z]/, 'Au moins une minuscule')
      .regex(/[0-9]/, 'Au moins un chiffre')
      .regex(/[^A-Za-z0-9]/, 'Au moins un caractère spécial'),
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'Les mots de passe ne correspondent pas',
    path: ['confirm_password'],
  })

type PasswordForm = z.infer<typeof passwordSchema>

const passwordRequirements = [
  { regex: /.{12,}/, label: 'Au moins 12 caractères' },
  { regex: /[A-Z]/, label: 'Une majuscule' },
  { regex: /[a-z]/, label: 'Une minuscule' },
  { regex: /[0-9]/, label: 'Un chiffre' },
  { regex: /[^A-Za-z0-9]/, label: 'Un caractère spécial' },
]

function PasskeysSection() {
  const { data: credentials, isLoading } = useWebAuthnCredentials()
  const registerMut = useRegisterWebAuthn()
  const deleteMut = useDeleteWebAuthnCredential()
  const [deviceName, setDeviceName] = useState('')
  const [showRegister, setShowRegister] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const supportsWebAuthn = typeof window !== 'undefined' && !!window.PublicKeyCredential

  const handleRegister = () => {
    if (!deviceName.trim()) return
    setError(null)
    registerMut.mutate(
      { deviceName: deviceName.trim() },
      {
        onSuccess: () => { setShowRegister(false); setDeviceName('') },
        onError: (err) => setError(normalizeError(err).message || 'Echec de l\'enregistrement'),
      }
    )
  }

  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-lg bg-primary-500/10 flex items-center justify-center">
            <Fingerprint className="w-6 h-6 text-primary-500" />
          </div>
          <div>
            <h3 className="font-semibold">Cles de securite (Passkeys)</h3>
            <p className="text-sm text-dark-400 mt-1">
              {supportsWebAuthn
                ? 'YubiKey, Touch ID, Windows Hello'
                : 'Non supporte par ce navigateur'}
            </p>
          </div>
        </div>
        {supportsWebAuthn && (
          <button
            onClick={() => setShowRegister(v => !v)}
            className="btn btn-secondary flex items-center gap-1 text-sm"
          >
            <Plus className="w-4 h-4" />
            Ajouter
          </button>
        )}
      </div>

      {error && (
        <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>
      )}

      {showRegister && (
        <div className="mt-4 p-4 rounded-lg border border-dark-600 space-y-3">
          <label className="block text-sm font-medium">Nom du peripherique</label>
          <input
            type="text"
            value={deviceName}
            onChange={e => setDeviceName(e.target.value)}
            placeholder="Ex: YubiKey bureau, Touch ID MacBook..."
            className="input w-full"
          />
          <div className="flex gap-2">
            <button
              onClick={handleRegister}
              disabled={!deviceName.trim() || registerMut.isPending}
              className="btn btn-primary text-sm disabled:opacity-40"
            >
              {registerMut.isPending ? 'Enregistrement...' : 'Enregistrer la cle'}
            </button>
            <button onClick={() => setShowRegister(false)} className="btn btn-secondary text-sm">Annuler</button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="mt-4 space-y-2">
          {[1, 2].map(i => <div key={i} className="h-12 bg-dark-800 rounded animate-pulse" />)}
        </div>
      ) : credentials && credentials.length > 0 ? (
        <div className="mt-4 space-y-2">
          {credentials.map(cred => (
            <div key={cred.id} className="flex items-center justify-between p-3 rounded-lg border border-dark-600 bg-dark-800/50">
              <div>
                <p className="text-sm font-medium">{cred.device_name}</p>
                <p className="text-xs text-dark-400">
                  Ajoutee le {new Date(cred.created_at).toLocaleDateString('fr-FR')}
                  {cred.last_used_at && ` · Derniere utilisation ${new Date(cred.last_used_at).toLocaleDateString('fr-FR')}`}
                </p>
              </div>
              <button
                onClick={() => deleteMut.mutate(cred.id)}
                disabled={deleteMut.isPending}
                className="p-2 text-dark-400 hover:text-red-400 disabled:opacity-40"
                title="Supprimer"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-dark-400">Aucune cle de securite enregistree.</p>
      )}
    </div>
  )
}

export default function SecurityPage() {
  const { user, fetchUser } = useAuthStore()
  const navigate = useNavigate()
  const passwordChangeRequired = user?.password_change_required === true
  const { data: mfaStatus, error: mfaStatusError } = useMfaStatus()
  const changePassword = useChangePassword()
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
  })
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mfaEnabled = mfaStatus?.enabled === true

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
  })

  const newPassword = watch('new_password', '')

  const onSubmit = async (data: PasswordForm) => {
    setError(null)
    try {
      await changePassword.mutateAsync({
        currentPassword: data.current_password,
        newPassword: data.new_password,
      })
      setSuccess(true)
      reset()

      // Rafraîchir le user (silencieux — le token actuel reste valide)
      try { await fetchUser() } catch { /* session toujours valide */ }

      // Si changement obligatoire, rediriger vers le dashboard après 1.5s
      if (passwordChangeRequired) {
        setTimeout(() => navigate({ to: '/dashboard' }), 1500)
      } else {
        setTimeout(() => setSuccess(false), 3000)
      }
    } catch (err: unknown) {
      setError(normalizeError(err).message || 'Erreur lors du changement')
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      {/* Header */}
      <PageHeader title="Sécurité" subtitle="Gérez la securite de votre compte" />

      {/* Bannière changement de mot de passe obligatoire */}
      {passwordChangeRequired && (
        <div className="flex items-start gap-4 p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
          <ShieldAlert className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-yellow-400">Changement de mot de passe obligatoire</p>
            <p className="text-sm text-dark-300 mt-1">
              Votre mot de passe a été détecté dans une fuite de données connue.
              Vous devez le changer avant de pouvoir continuer à utiliser l'application.
            </p>
          </div>
        </div>
      )}

      {/* Erreur récupération statut MFA */}
      {mfaStatusError && (
        <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {normalizeError(mfaStatusError).message || 'Impossible de récupérer le statut MFA'}
        </div>
      )}

      {/* 2FA Status */}
      <div
        className={cn(
          'card',
          mfaEnabled ? 'border-green-500/20' : 'border-yellow-500/20'
        )}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div
              className={cn(
                'w-12 h-12 rounded-lg flex items-center justify-center',
                mfaEnabled ? 'bg-green-500/10' : 'bg-yellow-500/10'
              )}
            >
              <Shield
                className={cn(
                  'w-6 h-6',
                  mfaEnabled ? 'text-green-500' : 'text-yellow-500'
                )}
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">Authentification à deux facteurs</h3>
                {mfaEnabled && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/10 text-green-500">
                    <Check className="w-3 h-3" />
                    Activé
                  </span>
                )}
              </div>
              <p className="text-sm text-dark-400 mt-1">
                {mfaEnabled
                  ? 'Votre compte est protégé par 2FA'
                  : "Ajoutez une couche de sécurité supplémentaire"}
              </p>
            </div>
          </div>
          <Link
            to="/profile/mfa"
            className={cn(
              'btn',
              mfaEnabled ? 'btn-secondary' : 'btn-primary'
            )}
          >
            {mfaEnabled ? 'Gérer' : 'Activer'}
          </Link>
        </div>
      </div>

      {/* Passkeys / WebAuthn */}
      <PasskeysSection />

      {/* Change Password */}
      <div className="card">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-10 h-10 rounded-lg bg-primary-500/10 flex items-center justify-center">
            <Key className="w-5 h-5 text-primary-500" />
          </div>
          <div>
            <h3 className="font-semibold">Changer le mot de passe</h3>
            <p className="text-sm text-dark-400">
              Mettez à jour votre mot de passe régulièrement
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {success && (
            <div className="flex items-center gap-2 p-4 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">
              <Check className="w-4 h-4" />
              Mot de passe modifié avec succès
            </div>
          )}

          {error && (
            <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm text-dark-400 mb-1">Mot de passe actuel</label>
            <div className="relative">
              <input
                type={showPasswords.current ? 'text' : 'password'}
                className={cn(
                  'input pr-10',
                  errors.current_password && 'input-error'
                )}
                {...register('current_password')}
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-dark-50"
                onClick={() =>
                  setShowPasswords((p) => ({ ...p, current: !p.current }))
                }
              >
                {showPasswords.current ? (
                  <EyeOff className="w-5 h-5" />
                ) : (
                  <Eye className="w-5 h-5" />
                )}
              </button>
            </div>
            {errors.current_password && (
              <p className="mt-1 text-sm text-red-400">
                {errors.current_password.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">Nouveau mot de passe</label>
            <div className="relative">
              <input
                type={showPasswords.new ? 'text' : 'password'}
                className={cn('input pr-10', errors.new_password && 'input-error')}
                {...register('new_password')}
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-dark-50"
                onClick={() =>
                  setShowPasswords((p) => ({ ...p, new: !p.new }))
                }
              >
                {showPasswords.new ? (
                  <EyeOff className="w-5 h-5" />
                ) : (
                  <Eye className="w-5 h-5" />
                )}
              </button>
            </div>

            <div className="mt-2 space-y-1">
              {passwordRequirements.map((req, i) => (
                <div
                  key={i}
                  className={cn(
                    'flex items-center gap-2 text-xs',
                    req.regex.test(newPassword)
                      ? 'text-green-400'
                      : 'text-dark-500'
                  )}
                >
                  {req.regex.test(newPassword) ? (
                    <Check className="w-3 h-3" />
                  ) : (
                    <X className="w-3 h-3" />
                  )}
                  {req.label}
                </div>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm text-dark-400 mb-1">Confirmer le nouveau mot de passe</label>
            <input
              type="password"
              className={cn('input', errors.confirm_password && 'input-error')}
              {...register('confirm_password')}
            />
            {errors.confirm_password && (
              <p className="mt-1 text-sm text-red-400">
                {errors.confirm_password.message}
              </p>
            )}
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Modification...
                </>
              ) : (
                'Changer le mot de passe'
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Sessions Link */}
      <div className="card">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-lg bg-dark-950 flex items-center justify-center">
              <Monitor className="w-5 h-5 text-dark-400" />
            </div>
            <div>
              <h3 className="font-semibold">Sessions actives</h3>
              <p className="text-sm text-dark-400">
                Consultez et gérez vos sessions connectées
              </p>
            </div>
          </div>
          <Link to="/profile/sessions" className="btn-secondary">
            Voir les sessions
          </Link>
        </div>
      </div>
    </div>
  )
}
