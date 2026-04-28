import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'
import { fetchAuthMe } from '@/api/queries/useAuth'
import { fetchMyProfile } from '@/api/queries/useUsers'
import { configureAuthStoreApiBridge, refreshAccessTokenFromBridge } from '@/api/queries/clientBridge'
import { useUIStore } from './uiStore'
import { tokenStore } from './tokenStore'

// Deduplication — évite double appel concurrent (onRehydrateStorage + beforeLoad)
let _initPromise: Promise<void> | null = null
// Cache initialize() pendant 5min pour éviter de rappeler /me à chaque navigation SPA
let _initCacheExpiry = 0
const INIT_CACHE_TTL = 5 * 60 * 1000 // 5 minutes

/**
 * Convergence ERR-006:
 * - `auth/me` reste la source de vérité pour RBAC (`permissions`, rôle effectif)
 * - `users/me` fournit les champs profil éditables
 */
async function getCanonicalUser(): Promise<User> {
  // Paralléliser auth/me + users/me — économise ~100ms de latence réseau
  const [authResult, profileResult] = await Promise.allSettled([
    fetchAuthMe(),
    fetchMyProfile(),
  ])
  if (authResult.status === 'rejected') throw authResult.reason
  const authUser = authResult.value
  if (profileResult.status === 'fulfilled') {
    return {
      ...authUser,
      ...profileResult.value,
      // Scopes/permissions restent pilotés par auth/me
      permissions: authUser.permissions,
      role: authUser.role,
    }
  }
  // Si /users/me est indisponible, on conserve une auth robuste.
  return authUser
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  mfaSessionToken: string | null
  /** device_id extrait du claim 'did' du JWT access token (§01 v3). */
  currentDid: string | null
  /** session_id extrait du claim 'sid' du JWT access token (décision D2 §06 §6.12). */
  currentSid: string | null

  // Actions
  setTokens: (accessToken: string, refreshToken?: string) => void
  setUser: (user: User) => void
  setMfaSessionToken: (token: string) => void
  logout: () => void
  fetchUser: () => Promise<void>
  initialize: () => Promise<void>
}

/** Décode les claims publics d'un JWT sans vérification de signature (côté client). */
function _decodeJwtClaims(token: string): { did?: string; sid?: string } {
  try {
    const base64 = token.split('.')[1]
    if (!base64) return {}
    const json = atob(base64.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json)
  } catch {
    return {}
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      mfaSessionToken: null,
      currentDid: null,
      currentSid: null,

      setTokens: (accessToken, _refreshToken?) => {
        tokenStore.setAccessToken(accessToken)
        // Extraire did + sid depuis les claims JWT (§01 v3 + décision D2 §06)
        const { did, sid } = _decodeJwtClaims(accessToken)
        // refreshToken géré côté backend via httpOnly cookie (S4)
        set({ isAuthenticated: true, currentDid: did ?? null, currentSid: sid ?? null })
        // CSRF est géré par initialize() — pas de double appel ici
      },

      setUser: (user) => {
        set({ user })
      },

      setMfaSessionToken: (token) => {
        set({ mfaSessionToken: token })
      },

      logout: () => {
        tokenStore.clear()
        set({
          user: null,
          isAuthenticated: false,
          mfaSessionToken: null,
          currentDid: null,
          currentSid: null,
        })
        useUIStore.getState().clearCsrfToken()
      },

      fetchUser: async () => {
        try {
          const user = await getCanonicalUser()
          set({ user, isAuthenticated: true, isLoading: false })
          // Alimenter le cache init pour éviter un double appel dans initialize()
          // lors de la navigation post-login (guard _app.tsx)
          _initCacheExpiry = Date.now() + INIT_CACHE_TTL
        } catch {
          // Auth 401 → refresh fail → fetchClient.onUnauthorized() déjà appelé
          //   (clear state + dispatch auth:session-expired → redirect /login)
          // Erreur réseau : garder l'état user actuel, ne pas forcer logout
        }
      },

      initialize: async () => {
        // Si déjà initialisé récemment (30s), skip le round-trip serveur
        if (_initPromise) return _initPromise
        if (_initCacheExpiry > Date.now() && get().isAuthenticated && get().user) {
          return
        }
        _initPromise = (async () => {
          try {
            // Si pas de token en mémoire (ex: page reload), refresh d'abord
            // pour éviter le waterfall /me→401→/refresh→/me (3 requêtes → 2)
            if (!tokenStore.getAccessToken()) {
              const newToken = await refreshAccessTokenFromBridge()
              tokenStore.setAccessToken(newToken)
              const { did, sid } = _decodeJwtClaims(newToken)
              set({ isAuthenticated: true, currentDid: did ?? null, currentSid: sid ?? null })
            }
            const timeout = new Promise<never>((_, rej) =>
              setTimeout(() => rej(new Error('init-timeout')), 5000)
            )
            const user = await Promise.race([getCanonicalUser(), timeout])
            set({ user, isAuthenticated: true, isLoading: false })
            _initCacheExpiry = Date.now() + INIT_CACHE_TTL
            // CSRF : ne refetch que si absent (le token est persisté dans localStorage)
            await useUIStore.getState().ensureCsrfToken()
          } catch {
            get().logout()
            set({ isLoading: false })
          } finally {
            _initPromise = null
          }
        })()
        return _initPromise
      },
    }),
    {
      name: 'marveline-auth',
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        // mfaSessionToken exclu : mémoire uniquement, TTL 300s Redis-SEC côté serveur (NC-08)
      }),
      onRehydrateStorage: () => (_state) => {
        // initialize() est géré exclusivement par _app.tsx:beforeLoad (awaited)
        // Ne pas appeler ici — évite la race condition double-initialize
      },
    }
  )
)

// Brise le cycle fetchClient ↔ authStore/uiStore via injection de dépendances.
// Doit être après la définition du store pour que les closures soient valides.
configureAuthStoreApiBridge({
  onTokenRefreshed: (token: string) => useAuthStore.getState().setTokens(token, ''),
  onUnauthorized: () => useAuthStore.getState().logout(),
  getCSRF: () => useUIStore.getState().csrfToken,
  fetchCSRF: () => useUIStore.getState().fetchCsrfToken(),
})
