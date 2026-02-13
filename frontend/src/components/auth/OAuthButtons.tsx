import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import apiClient from '@/api/client'

interface OAuthProvider {
  provider: string
  name: string
  icon: string
  color: string
  enabled: boolean
}

interface OAuthButtonsProps {
  onError?: (error: string) => void
  disabled?: boolean
}

// Icones SVG pour les providers
const ProviderIcons: Record<string, JSX.Element> = {
  google: (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path
        fill="currentColor"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="currentColor"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="currentColor"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="currentColor"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  ),
  github: (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
    </svg>
  ),
  facebook: (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
    </svg>
  ),
}

const ProviderColors: Record<string, string> = {
  google: 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50',
  github: 'bg-[#24292E] text-white hover:bg-[#2c3237]',
  facebook: 'bg-[#1877F2] text-white hover:bg-[#166fe5]',
}

export default function OAuthButtons({ onError, disabled }: OAuthButtonsProps) {
  const [providers, setProviders] = useState<OAuthProvider[]>([])
  const [loading, setLoading] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)

  // Charger les providers disponibles au premier rendu
  useEffect(() => {
    if (loaded) {
      return
    }

    let isActive = true

    apiClient
      .get('/oauth/providers')
      .then((res) => {
        if (!isActive) return
        setProviders(res.data.providers || [])
        setLoaded(true)
      })
      .catch(() => {
        if (!isActive) return
        // Silently fail - OAuth might not be configured
        setLoaded(true)
      })

    return () => {
      isActive = false
    }
  }, [loaded])

  const handleOAuthClick = async (provider: string) => {
    setLoading(provider)
    try {
      const response = await apiClient.get(`/oauth/${provider}/authorize`)
      const { auth_url } = response.data

      // Rediriger vers le provider OAuth
      window.location.href = auth_url
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      onError?.(error.response?.data?.detail || `Erreur ${provider}`)
      setLoading(null)
    }
  }

  if (!loaded || providers.length === 0) {
    return null
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-dark-600" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="px-2 bg-dark-800 text-dark-400">
            Ou continuer avec
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2">
        {providers.map((provider) => (
          <button
            key={provider.provider}
            type="button"
            disabled={disabled || loading !== null}
            onClick={() => handleOAuthClick(provider.provider)}
            className={`
              flex items-center justify-center gap-3 w-full px-4 py-2.5 rounded-lg
              font-medium transition-all duration-200
              ${ProviderColors[provider.provider] || 'bg-dark-700 text-white hover:bg-dark-600'}
              disabled:opacity-50 disabled:cursor-not-allowed
            `}
          >
            {loading === provider.provider ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              ProviderIcons[provider.provider]
            )}
            <span>Continuer avec {provider.name}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
