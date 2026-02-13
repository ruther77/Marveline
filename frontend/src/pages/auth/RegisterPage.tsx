import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, Loader2, Check, X } from 'lucide-react'
import { authApi } from '@/api/auth'
import { cn } from '@/lib/utils'
import OAuthButtons from '@/components/auth/OAuthButtons'

const registerSchema = z
  .object({
    first_name: z.string().min(2, 'Prénom trop court'),
    last_name: z.string().min(2, 'Nom trop court'),
    email: z.string().email('Email invalide'),
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

type RegisterForm = z.infer<typeof registerSchema>

const passwordRequirements = [
  { regex: /.{12,}/, label: 'Au moins 12 caractères' },
  { regex: /[A-Z]/, label: 'Une majuscule' },
  { regex: /[a-z]/, label: 'Une minuscule' },
  { regex: /[0-9]/, label: 'Un chiffre' },
  { regex: /[^A-Za-z0-9]/, label: 'Un caractère spécial' },
]

export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const navigate = useNavigate()

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
  })

  const password = watch('password', '')

  const onSubmit = async (data: RegisterForm) => {
    setError(null)
    try {
      await authApi.register({
        email: data.email,
        password: data.password,
        first_name: data.first_name,
        last_name: data.last_name,
      })
      setSuccess(true)
      setTimeout(() => navigate('/login'), 2000)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string; message?: string } } }
      setError(error.response?.data?.detail || error.response?.data?.message || "Erreur lors de l'inscription")
    }
  }

  if (success) {
    return (
      <div className="text-center space-y-4">
        <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto">
          <Check className="w-8 h-8 text-green-500" />
        </div>
        <h2 className="text-2xl font-bold">Compte créé !</h2>
        <p className="text-dark-400">
          Votre compte a été créé avec succès. Redirection vers la connexion...
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Créer un compte</h2>
        <p className="text-dark-400 mt-2">
          Rejoignez Marveline pour sécuriser votre infrastructure
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="first_name" className="label">
              Prénom
            </label>
            <input
              id="first_name"
              type="text"
              className={cn('input', errors.first_name && 'input-error')}
              placeholder="Jean"
              {...register('first_name')}
            />
            {errors.first_name && (
              <p className="mt-1 text-sm text-red-400">
                {errors.first_name.message}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="last_name" className="label">
              Nom
            </label>
            <input
              id="last_name"
              type="text"
              className={cn('input', errors.last_name && 'input-error')}
              placeholder="Dupont"
              {...register('last_name')}
            />
            {errors.last_name && (
              <p className="mt-1 text-sm text-red-400">
                {errors.last_name.message}
              </p>
            )}
          </div>
        </div>

        <div>
          <label htmlFor="email" className="label">
            Email
          </label>
          <input
            id="email"
            type="email"
            className={cn('input', errors.email && 'input-error')}
            placeholder="vous@exemple.com"
            {...register('email')}
          />
          {errors.email && (
            <p className="mt-1 text-sm text-red-400">{errors.email.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="password" className="label">
            Mot de passe
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

          {/* Password requirements */}
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
              Création...
            </>
          ) : (
            'Créer mon compte'
          )}
        </button>
      </form>

      <OAuthButtons
        onError={(err) => setError(err)}
        disabled={isSubmitting}
      />

      <p className="text-center text-dark-400 text-sm">
        Déjà un compte ?{' '}
        <Link to="/login" className="link">
          Se connecter
        </Link>
      </p>
    </div>
  )
}
