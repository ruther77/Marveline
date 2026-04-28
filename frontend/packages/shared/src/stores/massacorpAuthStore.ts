/**
 * massacorpAuthStore — store auth MassaCorp (restaurant + épicerie).
 *
 * Utilise createApiClient (shared) au lieu de massacorpClient (legacy).
 * Persist key 'massacorp-auth' partagée SSO entre restaurant et épicerie.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { massacorpTokenStore } from './massacorpTokenStore'
import { createApiClient } from '../api/client'
import type { ApiClient } from '../api/client'
import { AuthError } from '../errors/types'

// ── Types ────────────────────────────────────────────────────────────────────

export type MassaCorpTenant = 'restaurant' | 'epicerie'

export interface MassaCorpUser {
  id: number
  email: string
  first_name: string
  last_name: string
  role: string
  tenant_id: number
  scopes: string[]
}

interface AccountInfoV2 {
  account_id: number
  email: string
  first_name: string
  last_name: string
  tenant_id: number
  role_name: string
  scopes?: string[]
}

function mapAccountInfoToMassaCorpUser(info: AccountInfoV2): MassaCorpUser {
  return {
    id: info.account_id,
    email: info.email,
    first_name: info.first_name,
    last_name: info.last_name,
    role: info.role_name,
    tenant_id: info.tenant_id,
    scopes: info.scopes ?? [],
  }
}

interface MassaCorpAuthState {
  user: MassaCorpUser | null
  isAuthenticated: boolean
  isLoading: boolean
  csrfToken: string | null
  activeTenant: MassaCorpTenant

  setTokens: (accessToken: string) => void
  setUser: (user: MassaCorpUser) => void
  logout: () => void
  fetchUser: () => Promise<void>
  initialize: () => Promise<void>
  fetchCsrfToken: () => Promise<void>
  switchTenant: (tenant: MassaCorpTenant) => Promise<void>
}

// ── Config injectable par l'app ──────────────────────────────────────────────

export interface MassaCorpAuthConfig {
  /** VITE_MASSACORP_AUTH_TENANT_ID */
  authTenantId: string
  /** VITE_MASSACORP_RESTAURANT_TENANT_ID */
  restaurantTenantId: string
  /** VITE_MASSACORP_EPICERIE_TENANT_ID */
  epicerieTenantId: string
  /** VITE_API_URL (default '/api/v1') */
  apiUrl?: string
  /**
   * ISO-APP-01 : app_code statique si toute l'app est une seule app
   * ('epicerie' ou 'restaurant'). Pour un host multi-app (SSO), utiliser
   * getAppCode dérivé de activeTenant.
   */
  appCode?: string
}

let _config: MassaCorpAuthConfig = {
  authTenantId: '',
  restaurantTenantId: '',
  epicerieTenantId: '',
}

let _api: ApiClient | null = null

function getApi(): ApiClient {
  if (!_api) throw new Error('massacorpAuthStore: call configureMassaCorpAuth() before use')
  return _api
}

// ── Deduplication ────────────────────────────────────────────────────────────

let _initPromise: Promise<void> | null = null
let _initCacheExpiry = 0

// ── Helpers ──────────────────────────────────────────────────────────────────

function tenantIdFromActive(t: MassaCorpTenant): string {
  return t === 'restaurant' ? _config.restaurantTenantId : _config.epicerieTenantId
}

// ── Store ────────────────────────────────────────────────────────────────────

export const useMassaCorpAuthStore = create<MassaCorpAuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      csrfToken: null,
      activeTenant: 'epicerie' as MassaCorpTenant,

      setTokens: (accessToken) => {
        massacorpTokenStore.setAccessToken(accessToken)
        set({ isAuthenticated: true })
      },

      setUser: (user) => set({ user }),

      logout: () => {
        massacorpTokenStore.clear()
        set({
          user: null,
          isAuthenticated: false,
          csrfToken: null,
          // activeTenant conservé — chaque app garde son contexte
        })
      },

      switchTenant: async (tenant) => {
        if (get().activeTenant === tenant) return
        set({ activeTenant: tenant })
        const tenantId = tenantIdFromActive(tenant)
        if (!tenantId) return
        try {
          const newToken = await getApi().switchMembershipToken(tenantId)
          massacorpTokenStore.setAccessToken(newToken)
        } catch (err) {
          console.warn('[MassaCorp] switch-membership failed, keeping current token:', err)
        }
      },

      fetchCsrfToken: async () => {
        try {
          const data = await getApi().get<{ csrf_token: string }>('/auth/csrf')
          set({ csrfToken: data.csrf_token })
        } catch {
          // CSRF non bloquant — les mutations échoueront avec 403 et retry
        }
      },

      fetchUser: async () => {
        try {
          const info = await getApi().get<AccountInfoV2>('/auth/v2/me')
          set({ user: mapAccountInfoToMassaCorpUser(info) })
        } catch {
          // Erreur réseau : garder l'état actuel
        }
      },

      initialize: async () => {
        if (_initPromise) return _initPromise
        if (_initCacheExpiry > Date.now() && get().isAuthenticated && get().user) {
          return
        }
        _initPromise = (async () => {
          try {
            if (!massacorpTokenStore.getAccessToken()) {
              const newToken = await getApi().refreshAccessToken()
              massacorpTokenStore.setAccessToken(newToken)
              set({ isAuthenticated: true })
            }
            const timeout = new Promise<never>((_, rej) =>
              setTimeout(() => rej(new Error('init-timeout')), 5000)
            )
            const info = await Promise.race([
              getApi().get<AccountInfoV2>('/auth/v2/me'),
              timeout,
            ])
            const user = mapAccountInfoToMassaCorpUser(info)
            set({ user, isAuthenticated: true, isLoading: false })
            _initCacheExpiry = Date.now() + 30_000
            await get().fetchCsrfToken()
          } catch (err) {
            // Ne logout que sur un vrai 401 — les 500/timeout/réseau ne doivent
            // pas invalider la session (le backend peut être momentanément lent).
            if (err instanceof AuthError) {
              get().logout()
            }
            set({ isLoading: false })
          } finally {
            _initPromise = null
          }
        })()
        return _initPromise
      },
    }),
    {
      name: 'massacorp-auth',
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        activeTenant: state.activeTenant,
      }),
    }
  )
)

// ── Configuration (appelée au bootstrap de chaque app) ───────────────────────

export function configureMassaCorpAuth(config: MassaCorpAuthConfig): ApiClient {
  _config = config

  _api = createApiClient({
    apiUrl: config.apiUrl || '/api/v1',
    authTenantId: config.authTenantId,
    getActiveTenantId: () => {
      const { activeTenant } = useMassaCorpAuthStore.getState()
      return tenantIdFromActive(activeTenant)
    },
    // ISO-APP-01 : si `appCode` statique fourni → fixed, sinon dérive de activeTenant
    appCode: config.appCode,
    getActiveAppCode: config.appCode ? undefined : () => {
      const { activeTenant } = useMassaCorpAuthStore.getState()
      return activeTenant  // 'restaurant' | 'epicerie'
    },
    getAccessToken: () => massacorpTokenStore.getAccessToken(),
    getCsrfToken: () => useMassaCorpAuthStore.getState().csrfToken,
    fetchCsrfToken: () => useMassaCorpAuthStore.getState().fetchCsrfToken(),
    onTokenRefreshed: (token) => useMassaCorpAuthStore.getState().setTokens(token),
    onUnauthorized: () => useMassaCorpAuthStore.getState().logout(),
    sessionExpiredEvent: 'massacorp:session-expired',
  })

  return _api
}

/** Accès direct à l'instance API (après configureMassaCorpAuth) */
export function getMassaCorpApi(): ApiClient {
  return getApi()
}
