import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'
import { authApi } from '@/api/auth'
import { useUIStore } from './uiStore'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  mfaSessionToken: string | null

  // Actions
  setTokens: (accessToken: string, refreshToken: string) => void
  setUser: (user: User) => void
  setMfaSessionToken: (token: string) => void
  logout: () => void
  fetchUser: () => Promise<void>
  initialize: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
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
        useUIStore.getState().fetchCsrfToken()
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
          isAuthenticated: false,
          mfaSessionToken: null,
        })
        // Nettoyer le CSRF token aussi
        useUIStore.getState().clearCsrfToken()
      },

      fetchUser: async () => {
        try {
          const user = await authApi.me()
          set({ user })
        } catch {
          get().logout()
        }
      },

      initialize: async () => {
        const { accessToken } = get()
        if (accessToken) {
          try {
            const user = await authApi.me()
            set({ user, isAuthenticated: true, isLoading: false })
            // Récupérer le CSRF token après initialisation
            await useUIStore.getState().fetchCsrfToken()
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
        mfaSessionToken: state.mfaSessionToken,
      }),
      onRehydrateStorage: () => (state) => {
        // Appelé après hydratation depuis localStorage
        // À ce moment, accessToken est correctement chargé
        if (state) {
          state.initialize()
        }
      },
    }
  )
)
