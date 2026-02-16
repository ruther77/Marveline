import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Mail, ArrowLeft, CheckCircle } from 'lucide-react'
import { authApi } from '@/api/auth'
import { cn } from '@/lib/utils'

const forgotSchema = z.object({
  email: z.string().email('Email invalide'),
})

type ForgotForm = z.infer<typeof forgotSchema>

export default function ForgotPasswordPage() {
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotForm>({
    resolver: zodResolver(forgotSchema),
  })

  const onSubmit = async (data: ForgotForm) => {
    setError(null)
    try {
      await authApi.forgotPassword(data.email)
      setSent(true)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      setError(error.response?.data?.message || 'Erreur lors de l\'envoi')
    }
  }

  if (sent) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold">Email envoye</h2>
          <p className="text-dark-400 mt-2">
            Si un compte existe avec cette adresse, vous recevrez un lien de reinitialisation.
          </p>
        </div>

        <Link to="/login" className="btn-primary w-full flex items-center justify-center gap-2">
          <ArrowLeft className="w-4 h-4" />
          Retour a la connexion
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <Mail className="w-12 h-12 text-primary-400 mx-auto mb-4" />
        <h2 className="text-2xl font-bold">Mot de passe oublie</h2>
        <p className="text-dark-400 mt-2">
          Entrez votre email pour recevoir un lien de reinitialisation
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        <div>
          <label htmlFor="email" className="label">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            className={cn('input', errors.email && 'input-error')}
            placeholder="vous@exemple.com"
            {...register('email')}
          />
          {errors.email && (
            <p className="mt-1 text-sm text-red-400">{errors.email.message}</p>
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
              Envoi...
            </>
          ) : (
            'Envoyer le lien'
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
