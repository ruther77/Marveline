import { useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, Loader2, Lock, CheckCircle } from 'lucide-react'
import { authApi } from '@/api/auth'
import { cn } from '@/lib/utils'

const resetSchema = z.object({
  password: z.string().min(8, 'Minimum 8 caracteres'),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: 'Les mots de passe ne correspondent pas',
  path: ['confirmPassword'],
})

type ResetForm = z.infer<typeof resetSchema>

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')

  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetForm>({
    resolver: zodResolver(resetSchema),
  })

  if (!token) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <Lock className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold">Lien invalide</h2>
          <p className="text-dark-400 mt-2">
            Le lien de reinitialisation est invalide ou a expire.
          </p>
        </div>
        <Link to="/forgot-password" className="btn-primary w-full block text-center">
          Demander un nouveau lien
        </Link>
      </div>
    )
  }

  const onSubmit = async (data: ResetForm) => {
    setError(null)
    try {
      await authApi.resetPassword(token, data.password)
      setSuccess(true)
      setTimeout(() => navigate('/login'), 3000)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      setError(error.response?.data?.message || 'Erreur lors de la reinitialisation')
    }
  }

  if (success) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold">Mot de passe modifie</h2>
          <p className="text-dark-400 mt-2">
            Redirection vers la connexion...
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <Lock className="w-12 h-12 text-primary-400 mx-auto mb-4" />
        <h2 className="text-2xl font-bold">Nouveau mot de passe</h2>
        <p className="text-dark-400 mt-2">
          Choisissez un nouveau mot de passe
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
              autoComplete="new-password"
              className={cn('input pr-10', errors.password && 'input-error')}
              placeholder="••••••••"
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
          {errors.password && (
            <p className="mt-1 text-sm text-red-400">{errors.password.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="confirmPassword" className="label">
            Confirmer le mot de passe
          </label>
          <input
            id="confirmPassword"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            className={cn('input', errors.confirmPassword && 'input-error')}
            placeholder="••••••••"
            {...register('confirmPassword')}
          />
          {errors.confirmPassword && (
            <p className="mt-1 text-sm text-red-400">{errors.confirmPassword.message}</p>
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
              Reinitialisation...
            </>
          ) : (
            'Reinitialiser le mot de passe'
          )}
        </button>
      </form>

      <p className="text-center">
        <Link to="/login" className="text-sm link">
          Retour a la connexion
        </Link>
      </p>
    </div>
  )
}
