import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'
import {
  Loader2,
  Eye,
  EyeOff,
  Check,
  X,
  Shield,
  Key,
  Monitor,
} from 'lucide-react'
import { cn } from '@/lib/utils'

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

export default function SecurityPage() {
  const { user } = useAuthStore()
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
  })
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
      await authApi.changePassword(data.current_password, data.new_password)
      setSuccess(true)
      reset()
      setTimeout(() => setSuccess(false), 3000)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      setError(error.response?.data?.message || 'Erreur lors du changement')
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Sécurité</h1>
        <p className="text-dark-400 mt-1">
          Gérez la sécurité de votre compte
        </p>
      </div>

      {/* 2FA Status */}
      <div
        className={cn(
          'card',
          user?.has_mfa ? 'border-green-500/20' : 'border-yellow-500/20'
        )}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div
              className={cn(
                'w-12 h-12 rounded-lg flex items-center justify-center',
                user?.has_mfa ? 'bg-green-500/10' : 'bg-yellow-500/10'
              )}
            >
              <Shield
                className={cn(
                  'w-6 h-6',
                  user?.has_mfa ? 'text-green-500' : 'text-yellow-500'
                )}
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">Authentification à deux facteurs</h3>
                {user?.has_mfa && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/10 text-green-500">
                    <Check className="w-3 h-3" />
                    Activé
                  </span>
                )}
              </div>
              <p className="text-sm text-dark-400 mt-1">
                {user?.has_mfa
                  ? 'Votre compte est protégé par 2FA'
                  : "Ajoutez une couche de sécurité supplémentaire"}
              </p>
            </div>
          </div>
          <Link
            to="/profile/mfa"
            className={cn(
              'btn',
              user?.has_mfa ? 'btn-secondary' : 'btn-primary'
            )}
          >
            {user?.has_mfa ? 'Gérer' : 'Activer'}
          </Link>
        </div>
      </div>

      {/* Change Password */}
      <div className="card">
        <div className="flex items-center gap-3 mb-6">
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
            <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm">
              <Check className="w-4 h-4" />
              Mot de passe modifié avec succès
            </div>
          )}

          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="label">Mot de passe actuel</label>
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
                className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-white"
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
            <label className="label">Nouveau mot de passe</label>
            <div className="relative">
              <input
                type={showPasswords.new ? 'text' : 'password'}
                className={cn('input pr-10', errors.new_password && 'input-error')}
                {...register('new_password')}
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-white"
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
            <label className="label">Confirmer le nouveau mot de passe</label>
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
            <div className="w-10 h-10 rounded-lg bg-dark-700 flex items-center justify-center">
              <Monitor className="w-5 h-5 text-dark-400" />
            </div>
            <div>
              <h3 className="font-semibold">Sessions actives</h3>
              <p className="text-sm text-dark-400">
                Consultez et gérez vos sessions connectées
              </p>
            </div>
          </div>
          <Link to="/admin/sessions" className="btn-secondary">
            Voir les sessions
          </Link>
        </div>
      </div>
    </div>
  )
}
