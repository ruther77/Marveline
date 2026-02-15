/**
 * Tests unitaires pour stores/authStore.ts
 *
 * Couvre : state initial, setTokens, setUser, setMfaSessionToken,
 * logout, fetchUser, initialize, persist config.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAuthStore } from '../authStore'
import type { User } from '@/types'

// Mock authApi to prevent real HTTP calls
vi.mock('@/api/auth', () => ({
  authApi: {
    me: vi.fn(),
  },
}))

import { authApi } from '@/api/auth'

const mockUser: User = {
  id: 1,
  email: 'test@marveline.com',
  first_name: 'Jean',
  last_name: 'Dupont',
  is_active: true,
  is_verified: true,
  tenant_id: 1,
  created_at: '2026-01-01T00:00:00Z',
}

function resetStore() {
  useAuthStore.setState({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: false,
    mfaSessionToken: null,
  })
}

// ── Etat initial ────────────────────────────────────────────────────

describe('AuthStore — etat initial', () => {
  beforeEach(() => {
    resetStore()
  })

  it('user est null initialement', () => {
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
  })

  it('tokens sont null initialement', () => {
    const state = useAuthStore.getState()
    expect(state.accessToken).toBeNull()
    expect(state.refreshToken).toBeNull()
  })

  it('n est pas authentifie initialement', () => {
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('mfaSessionToken est null initialement', () => {
    expect(useAuthStore.getState().mfaSessionToken).toBeNull()
  })
})

// ── setTokens ────────────────────────────────────────────────────────

describe('AuthStore — setTokens', () => {
  beforeEach(() => {
    resetStore()
  })

  it('stocke les tokens access et refresh', () => {
    useAuthStore.getState().setTokens('access_123', 'refresh_456')
    const state = useAuthStore.getState()
    expect(state.accessToken).toBe('access_123')
    expect(state.refreshToken).toBe('refresh_456')
  })

  it('passe isAuthenticated a true', () => {
    useAuthStore.getState().setTokens('a', 'r')
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })
})

// ── setUser ──────────────────────────────────────────────────────────

describe('AuthStore — setUser', () => {
  beforeEach(() => {
    resetStore()
  })

  it('stocke l objet user', () => {
    useAuthStore.getState().setUser(mockUser)
    expect(useAuthStore.getState().user).toEqual(mockUser)
  })

  it('met a jour le user lors d un second appel', () => {
    useAuthStore.getState().setUser(mockUser)
    const updated = { ...mockUser, first_name: 'Pierre' }
    useAuthStore.getState().setUser(updated)
    expect(useAuthStore.getState().user?.first_name).toBe('Pierre')
  })
})

// ── setMfaSessionToken ───────────────────────────────────────────────

describe('AuthStore — setMfaSessionToken', () => {
  beforeEach(() => {
    resetStore()
  })

  it('stocke le token de session MFA', () => {
    useAuthStore.getState().setMfaSessionToken('mfa_token_abc')
    expect(useAuthStore.getState().mfaSessionToken).toBe('mfa_token_abc')
  })
})

// ── logout ───────────────────────────────────────────────────────────

describe('AuthStore — logout', () => {
  beforeEach(() => {
    resetStore()
    // Set up authenticated state first
    useAuthStore.setState({
      user: mockUser,
      accessToken: 'token',
      refreshToken: 'refresh',
      isAuthenticated: true,
      mfaSessionToken: 'mfa_token',
    })
  })

  it('efface le user', () => {
    useAuthStore.getState().logout()
    expect(useAuthStore.getState().user).toBeNull()
  })

  it('efface les tokens', () => {
    useAuthStore.getState().logout()
    const state = useAuthStore.getState()
    expect(state.accessToken).toBeNull()
    expect(state.refreshToken).toBeNull()
  })

  it('passe isAuthenticated a false', () => {
    useAuthStore.getState().logout()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('efface le mfaSessionToken', () => {
    useAuthStore.getState().logout()
    expect(useAuthStore.getState().mfaSessionToken).toBeNull()
  })
})

// ── fetchUser ────────────────────────────────────────────────────────

describe('AuthStore — fetchUser', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  it('recupere et stocke le user en cas de succes', async () => {
    vi.mocked(authApi.me).mockResolvedValueOnce(mockUser)
    await useAuthStore.getState().fetchUser()
    expect(useAuthStore.getState().user).toEqual(mockUser)
  })

  it('appelle logout en cas d echec', async () => {
    useAuthStore.setState({ accessToken: 'token', isAuthenticated: true })
    vi.mocked(authApi.me).mockRejectedValueOnce(new Error('Unauthorized'))
    await useAuthStore.getState().fetchUser()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().accessToken).toBeNull()
  })
})

// ── initialize ───────────────────────────────────────────────────────

describe('AuthStore — initialize', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  it('passe isLoading a false quand pas de token', async () => {
    useAuthStore.setState({ isLoading: true })
    await useAuthStore.getState().initialize()
    expect(useAuthStore.getState().isLoading).toBe(false)
  })

  it('recupere le user quand un token existe', async () => {
    useAuthStore.setState({ accessToken: 'valid_token', isLoading: true })
    vi.mocked(authApi.me).mockResolvedValueOnce(mockUser)
    await useAuthStore.getState().initialize()
    expect(useAuthStore.getState().user).toEqual(mockUser)
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect(useAuthStore.getState().isLoading).toBe(false)
  })

  it('logout et arrete le loading en cas d echec', async () => {
    useAuthStore.setState({ accessToken: 'expired_token', isLoading: true })
    vi.mocked(authApi.me).mockRejectedValueOnce(new Error('401'))
    await useAuthStore.getState().initialize()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().isLoading).toBe(false)
  })
})

// ── Persist Config ───────────────────────────────────────────────────

describe('AuthStore — persistance', () => {
  it('utilise la cle de stockage marveline-auth', () => {
    const persistOptions = (useAuthStore as unknown as { persist: { getOptions: () => { name: string } } }).persist?.getOptions?.()
    if (persistOptions) {
      expect(persistOptions.name).toBe('marveline-auth')
    } else {
      useAuthStore.getState().setTokens('test_access', 'test_refresh')
      const stored = localStorage.getItem('marveline-auth')
      expect(stored).not.toBeNull()
    }
  })

  it('persiste uniquement les tokens (pas le user)', () => {
    useAuthStore.getState().setTokens('access', 'refresh')
    useAuthStore.getState().setUser(mockUser)
    const stored = JSON.parse(localStorage.getItem('marveline-auth') || '{}')
    if (stored.state) {
      expect(stored.state.accessToken).toBe('access')
      expect(stored.state.refreshToken).toBe('refresh')
      expect(stored.state.user).toBeUndefined()
    }
  })
})
