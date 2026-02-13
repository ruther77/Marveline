import { useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Eye, EyeOff, Check, X, ArrowLeft } from 'lucide-react'
import { authApi } from '@/api/auth'
import { cn } from '@/lib/utils'

const resetPasswordSchema = z
  .object({
    password: z
      .string()
      .min(12, 'Minimum 12 caractères')
      .regex(/[A-Z]/, 'Au moins une majuscule')
      .regex(/[a-z]/, 'Au moins une minuscule')
      .regex(/[0-9]/, 'Au moins un chiffre')
      .regex(/[^A-Za-z0-9]/, 'Au moins un caractère spécial'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Les mots de passe ne correspondent pas',
    path: ['confirmPassword'],
  })

type ResetPasswordForm = z.infer<typeof resetPasswordSchema>

const passwordRequirements = [
  { regex: /.{12,}/, label: 'Au moins 12 caractères' },
  { regex: /[A-Z]/, label: 'Une majuscule' },
  { regex: /[a-z]/, label: 'Une minuscule' },
  { regex: /[0-9]/, label: 'Un chiffre' },
  { regex: /[^A-Za-z0-9]/, label: 'Un caractère spécial' },
]

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const navigate = useNavigate()

  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordForm>({
    resolver: zodResolver(resetPasswordSchema),
  })

  const password = watch('password', '')

  const onSubmit = async (data: ResetPasswordForm) => {
    if (!token) {
      setError('Token de réinitialisation manquant')
      return
    }

    setError(null)
    try {
      await authApi.resetPassword(token, data.password)
      setSuccess(true)
      setTimeout(() => navigate('/login'), 2000)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      setError(
        error.response?.data?.message ||
          'Erreur lors de la réinitialisation. Le lien a peut-être expiré.'
      )
    }
  }

  if (!token) {
    return (
      <div className="text-center space-y-4">
        <h2 className="text-2xl font-bold text-red-400">Lien invalide</h2>
        <p className="text-dark-400">
          Le lien de réinitialisation est invalide ou a expiré.
        </p>
        <Link to="/forgot-password" className="btn-primary inline-flex">
          Demander un nouveau lien
        </Link>
      </div>
    )
  }

  if (success) {
    return (
      <div className="text-center space-y-4">
        <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto">
          <Check className="w-8 h-8 text-green-500" />
        </div>
        <h2 className="text-2xl font-bold">Mot de passe réinitialisé</h2>
        <p className="text-dark-400">
          Votre mot de passe a été modifié. Redirection vers la connexion...
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Nouveau mot de passe</h2>
        <p className="text-dark-400 mt-2">
          Choisissez un nouveau mot de passe sécurisé
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        <div>
          <label htmlFor="password" className="label">
            Nouveau mot de passe
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              className={cn('input pr-10', errors.password && 'input-error')}
              placeholder="••••••••••••"
              {...register('password')}
            />
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-white"
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? (
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
                  req.regex.test(password) ? 'text-green-400' : 'text-dark-500'
                )}
              >
                {req.regex.test(password) ? (
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
          <label htmlFor="confirmPassword" className="label">
            Confirmer le mot de passe
          </label>
          <input
            id="confirmPassword"
            type="password"
            className={cn('input', errors.confirmPassword && 'input-error')}
            placeholder="••••••••••••"
            {...register('confirmPassword')}
          />
          {errors.confirmPassword && (
            <p className="mt-1 text-sm text-red-400">
              {errors.confirmPassword.message}
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="btn-primary w-full"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              Réinitialisation...
            </>
          ) : (
            'Réinitialiser le mot de passe'
          )}
        </button>
      </form>

      <p className="text-center">
        <Link to="/login" className="text-sm link inline-flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" />
          Retour à la connexion
        </Link>
      </p>
    </div>
  )
}
