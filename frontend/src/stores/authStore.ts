import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'
import { authApi } from '@/api/auth'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  csrfToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  mfaSessionToken: string | null

  // Actions
  setTokens: (accessToken: string, refreshToken: string) => void
  setCsrfToken: (token: string) => void
  setUser: (user: User) => void
  setMfaSessionToken: (token: string) => void
  logout: () => void
  fetchUser: () => Promise<void>
  fetchCsrfToken: () => Promise<void>
  initialize: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      csrfToken: null,
      isAuthenticated: false,
      isLoading: true,
      mfaSessionToken: null,

      setTokens: (accessToken, refreshToken) => {
        set({
          accessToken,
          refreshToken,
          isAuthenticated: true,
        })
        // Récupérer automatiquement le CSRF token après avoir défini les tokens
        get().fetchCsrfToken()
      },

      setCsrfToken: (token) => {
        set({ csrfToken: token })
      },

      setUser: (user) => {
        set({ user })
      },

      setMfaSessionToken: (token) => {
        set({ mfaSessionToken: token })
      },

      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          csrfToken: null,
          isAuthenticated: false,
          mfaSessionToken: null,
        })
      },

      fetchUser: async () => {
        try {
          const user = await authApi.me()
          set({ user })
        } catch {
          get().logout()
        }
      },

      fetchCsrfToken: async () => {
        try {
          const response = await authApi.getCsrfToken()
          set({ csrfToken: response.csrf_token })
          // Rafraîchir le token avant expiration (14 min, TTL backend = 15 min)
          setTimeout(() => {
            if (get().isAuthenticated) {
              get().fetchCsrfToken()
            }
          }, 14 * 60 * 1000)
        } catch {
          // Erreur silencieuse, le middleware renverra 403 et forcera une nouvelle tentative
          console.warn('Failed to fetch CSRF token')
        }
      },

      initialize: async () => {
        const { accessToken } = get()
        if (accessToken) {
          try {
            const user = await authApi.me()
            set({ user, isAuthenticated: true, isLoading: false })
            // Récupérer le CSRF token après initialisation
            get().fetchCsrfToken()
          } catch {
            get().logout()
            set({ isLoading: false })
          }
        } else {
          set({ isLoading: false })
        }
      },
    }),
    {
      name: 'marveline-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    }
  )
)

// Initialize on load
useAuthStore.getState().initialize()
