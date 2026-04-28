import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { massacorpTokenStore } from './massacorpTokenStore'
import { configureMassaCorpClient, refreshMassaCorpToken, massacorpApi, switchMembershipToken } from '@/api/massacorpClient'

// Deduplication — évite double appel concurrent
let _initPromise: Promise<void> | null = null
let _initCacheExpiry = 0

const RESTAURANT_TENANT_ID = import.meta.env.VITE_MASSACORP_RESTAURANT_TENANT_ID || ''
const EPICERIE_TENANT_ID   = import.meta.env.VITE_MASSACORP_EPICERIE_TENANT_ID   || ''

export type MassaCorpTenant = 'restaurant' | 'epicerie'

export interface MassaCorpUser {
  id: number
  email: string
  first_name: string
  last_name: string
  role: string
  tenant_id: number
}

interface AccountInfoV2 {
  account_id: number
  email: string
  first_name: string
  last_name: string
  tenant_id: number
  role_name: string
}

function mapAccountInfoToMassaCorpUser(info: AccountInfoV2): MassaCorpUser {
  return {
    id: info.account_id,
    email: info.email,
    first_name: info.first_name,
    last_name: info.last_name,
    role: info.role_name,
    tenant_id: info.tenant_id,
  }
}

interface MassaCorpAuthState {
  user: MassaCorpUser | null
  isAuthenticated: boolean
  isLoading: boolean
  csrfToken: string | null
  /** Entreprise active dans l'espace MassaCorp */
  activeTenant: MassaCorpTenant

  // Actions
  setTokens: (accessToken: string) => void
  setUser: (user: MassaCorpUser) => void
  logout: () => void
  fetchUser: () => Promise<void>
  initialize: () => Promise<void>
  fetchCsrfToken: () => Promise<void>
  switchTenant: (tenant: MassaCorpTenant) => Promise<void>
}

function tenantIdFromActive(t: MassaCorpTenant): string {
  return t === 'restaurant' ? RESTAURANT_TENANT_ID : EPICERIE_TENANT_ID
}

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
          activeTenant: 'epicerie',
        })
      },

      switchTenant: async (tenant) => {
        if (get().activeTenant === tenant) return
        set({ activeTenant: tenant })
        const tenantId = tenantIdFromActive(tenant)
        if (!tenantId) return
        try {
          const newToken = await switchMembershipToken(tenantId)
          massacorpTokenStore.setAccessToken(newToken)
        } catch (err) {
          // Échec non bloquant — les requêtes individuelles recevront 401 → refresh
          console.warn('[MassaCorp] switch-membership failed, keeping current token:', err)
        }
      },

      fetchCsrfToken: async () => {
        try {
          const data = await massacorpApi.get<{ csrf_token: string }>('/auth/csrf')
          set({ csrfToken: data.csrf_token })
        } catch {
          // CSRF non bloquant — les mutations échoueront avec 403 et retry
        }
      },

      fetchUser: async () => {
        try {
          const info = await massacorpApi.get<AccountInfoV2>('/auth/v2/me')
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
              const newToken = await refreshMassaCorpToken()
              massacorpTokenStore.setAccessToken(newToken)
              set({ isAuthenticated: true })
            }
            const timeout = new Promise<never>((_, rej) =>
              setTimeout(() => rej(new Error('init-timeout')), 5000)
            )
            const info = await Promise.race([
              massacorpApi.get<AccountInfoV2>('/auth/v2/me'),
              timeout,
            ])
            const user = mapAccountInfoToMassaCorpUser(info)
            set({ user, isAuthenticated: true, isLoading: false })
            _initCacheExpiry = Date.now() + 30_000
            await get().fetchCsrfToken()
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
      name: 'massacorp-auth',
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        activeTenant: state.activeTenant,
      }),
    }
  )
)

// Brise le cycle client ↔ store via injection de dépendances
configureMassaCorpClient({
  onTokenRefreshed: (token) => useMassaCorpAuthStore.getState().setTokens(token),
  onUnauthorized: () => useMassaCorpAuthStore.getState().logout(),
  getCSRF: () => useMassaCorpAuthStore.getState().csrfToken,
  fetchCSRF: () => useMassaCorpAuthStore.getState().fetchCsrfToken(),
  getActiveTenantId: () => {
    const { activeTenant } = useMassaCorpAuthStore.getState()
    return tenantIdFromActive(activeTenant)
  },
})
