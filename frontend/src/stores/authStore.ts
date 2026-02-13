import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'
import { authApi } from '@/api/auth'

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
