import { useEffect, useRef } from 'react'
import { useNavigate, useParams, useSearch } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/authStore'
import { useOAuthCallback } from '@/api/queries/useAuth'
import { normalizeError } from '@shared/errors/normalizer'

export default function OAuthCallbackPage() {
  const navigate = useNavigate()
  const { provider } = useParams({ strict: false }) as { provider?: string }
  const search = useSearch({ strict: false }) as { code?: string; state?: string; error?: string }
  const { setTokens, fetchUser } = useAuthStore()
  const calledRef = useRef(false)
  const oauthCallback = useOAuthCallback()

  useEffect(() => {
    if (calledRef.current) return
    calledRef.current = true

    const { code, state, error: oauthError } = search

    if (oauthError) {
      navigate({ to: '/login', search: { error: oauthError }, replace: true })
      return
    }

    if (!provider || !code || !state) {
      navigate({ to: '/login', search: { error: 'Paramètres OAuth manquants' }, replace: true })
      return
    }

    oauthCallback
      .mutateAsync({ provider, code, state })
      .then(async (response) => {
        setTokens(response.access_token)
        await fetchUser()
        navigate({ to: '/dashboard', replace: true })
      })
      .catch((err: unknown) => {
        const msg = normalizeError(err).message || 'Erreur de connexion OAuth'
        navigate({ to: '/login', search: { error: msg }, replace: true })
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen bg-dark-900 flex items-center justify-center">
      <div className="text-center space-y-4">
        <div className="w-16 h-16 mx-auto skel rounded-full animate-pulse" aria-hidden="true" />
        <div className="h-4 w-40 mx-auto skel rounded animate-pulse" aria-hidden="true" />
        <div className="h-3 w-28 mx-auto skel rounded animate-pulse" aria-hidden="true" />
        <p className="sr-only">Connexion OAuth en cours…</p>
      </div>
    </div>
  )
}
