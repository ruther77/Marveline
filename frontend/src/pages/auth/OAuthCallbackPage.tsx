import { useEffect, useState, useCallback } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Check, AlertCircle } from 'lucide-react'
import apiClient from '@/api/client'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/lib/utils'

const completeSchema = z.object({
  first_name: z.string().min(2, 'Prenom trop court'),
  last_name: z.string().min(2, 'Nom trop court'),
})

type CompleteForm = z.infer<typeof completeSchema>

interface OAuthResult {
  success: boolean
  requires_registration?: boolean
  oauth_session_token?: string
  access_token?: string
  refresh_token?: string
  provider?: string
  email?: string
  name?: string
  avatar_url?: string
}

export default function OAuthCallbackPage() {
  const { provider } = useParams<{ provider: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { setTokens, fetchUser } = useAuthStore()

  const [status, setStatus] = useState<'loading' | 'complete' | 'error' | 'needs_info'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [oauthData, setOauthData] = useState<OAuthResult | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setValue,
  } = useForm<CompleteForm>({
    resolver: zodResolver(completeSchema),
  })

  const handleCallback = useCallback(async (code: string, state: string) => {
    try {
      const response = await apiClient.get(`/oauth/${provider}/callback`, {
        params: { code, state },
      })

      const result: OAuthResult = response.data

      if (!result.success) {
        setError('Authentification echouee')
        setStatus('error')
        return
      }

      if (result.requires_registration) {
        // Nouvel utilisateur - demander les infos manquantes
        setOauthData(result)

        // Pre-remplir avec les infos du provider si disponibles
        if (result.name) {
          const parts = result.name.split(' ')
          setValue('first_name', parts[0] || '')
          setValue('last_name', parts.slice(1).join(' ') || '')
        }

        setStatus('needs_info')
      } else if (result.access_token && result.refresh_token) {
        // Utilisateur existant - login direct
        setTokens(result.access_token, result.refresh_token)
        await fetchUser()
        setStatus('complete')

        // Rediriger vers le dashboard
        setTimeout(() => navigate('/dashboard'), 1500)
      } else {
        setError('Reponse invalide du serveur')
        setStatus('error')
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Erreur lors de l\'authentification')
      setStatus('error')
    }
  }, [provider, setTokens, fetchUser, navigate, setValue])

  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const errorParam = searchParams.get('error')

    if (errorParam) {
      setError(`Authentification refusee: ${searchParams.get('error_description') || errorParam}`)
      setStatus('error')
      return
    }

    if (!code || !state) {
      setError('Parametres manquants')
      setStatus('error')
      return
    }

    // Appeler le callback backend
    handleCallback(code, state)
  }, [provider, searchParams, handleCallback])

  const onCompleteRegistration = async (data: CompleteForm) => {
    if (!oauthData?.oauth_session_token) return

    try {
      const response = await apiClient.post('/oauth/complete-registration', {
        oauth_session_token: oauthData.oauth_session_token,
        first_name: data.first_name,
        last_name: data.last_name,
      })

      const { access_token, refresh_token } = response.data

      setTokens(access_token, refresh_token)
      await fetchUser()
      setStatus('complete')

      // Rediriger vers le dashboard
      setTimeout(() => navigate('/dashboard'), 1500)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Erreur lors de l\'inscription')
    }
  }

  // Affichage selon le status
  if (status === 'loading') {
    return (
      <div className="text-center space-y-4">
        <Loader2 className="w-12 h-12 animate-spin mx-auto text-primary-500" />
        <h2 className="text-xl font-bold">Authentification en cours...</h2>
        <p className="text-dark-400">
          Veuillez patienter pendant que nous verifions vos informations.
        </p>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="text-center space-y-4">
        <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mx-auto">
          <AlertCircle className="w-8 h-8 text-red-500" />
        </div>
        <h2 className="text-2xl font-bold text-red-500">Erreur</h2>
        <p className="text-dark-400">{error}</p>
        <button
          onClick={() => navigate('/login')}
          className="btn-primary"
        >
          Retour a la connexion
        </button>
      </div>
    )
  }

  if (status === 'complete') {
    return (
      <div className="text-center space-y-4">
        <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto">
          <Check className="w-8 h-8 text-green-500" />
        </div>
        <h2 className="text-2xl font-bold">Connexion reussie !</h2>
        <p className="text-dark-400">
          Redirection vers votre tableau de bord...
        </p>
      </div>
    )
  }

  // needs_info - Formulaire pour completer l'inscription
  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Finaliser votre inscription</h2>
        <p className="text-dark-400 mt-2">
          Bienvenue ! Completez votre profil pour continuer.
        </p>
      </div>

      {oauthData?.email && (
        <div className="p-3 rounded-lg bg-dark-700 text-sm">
          <span className="text-dark-400">Email:</span>{' '}
          <span className="text-white">{oauthData.email}</span>
        </div>
      )}

      <form onSubmit={handleSubmit(onCompleteRegistration)} className="space-y-4">
        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="first_name" className="label">
              Prenom
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

        <button
          type="submit"
          disabled={isSubmitting}
          className="btn-primary w-full"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              Creation du compte...
            </>
          ) : (
            'Creer mon compte'
          )}
        </button>
      </form>
    </div>
  )
}
