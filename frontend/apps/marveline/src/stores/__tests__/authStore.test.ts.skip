/**
 * Tests unitaires pour stores/authStore.ts
 *
 * Couvre : state initial, setTokens, setUser, setMfaSessionToken,
 * logout, fetchUser, initialize, persist config.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useAuthStore } from '../authStore'
import type { User } from '@/types'

// Mock authApi to prevent real HTTP calls
vi.mock('@/api/auth', () => ({
  authApi: {
    me: vi.fn(),
    getCsrfToken: vi.fn(),
  },
}))

import { authApi } from '@/api/auth'

const mockUser: User = {
  id: 1,
  email: 'test@marveline.com',
  full_name: 'Jean Dupont',
  role: 'staff',
  tenant_id: 1,
  is_active: true,
  permissions: [],
  created_at: '2026-01-01T00:00:00Z',
  first_name: 'Jean',
  last_name: 'Dupont',
}

function resetStore() {
  useAuthStore.setState({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: false,
    mfaSessionToken: null,
    csrfToken: null,
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

// ── CSRF Token Management ────────────────────────────────────────────

describe('AuthStore — fetchCsrfToken', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
    vi.clearAllTimers()
    vi.useFakeTimers()
    // Mock authApi.me pour empêcher initialize() d'interférer
    vi.mocked(authApi.me).mockRejectedValue(new Error('Not authenticated'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('appelle GET /auth/csrf et stocke le token dans le state', async () => {
    const mockToken = 'csrf-token-abc123'
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: mockToken })

    await useAuthStore.getState().fetchCsrfToken()

    expect(authApi.getCsrfToken).toHaveBeenCalledOnce()
    expect(useAuthStore.getState().csrfToken).toBe(mockToken)
  })

  it('programme un auto-refresh apres 14 minutes si authentifie', async () => {
    const mockToken = 'csrf-token-abc123'
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: mockToken })

    // Simuler utilisateur authentifié
    useAuthStore.setState({ isAuthenticated: true })

    await useAuthStore.getState().fetchCsrfToken()
    const callsBeforeRefresh = vi.mocked(authApi.getCsrfToken).mock.calls.length

    // Avancer de 14 minutes - 1 seconde (pas encore déclenché)
    vi.advanceTimersByTime(14 * 60 * 1000 - 1000)
    expect(authApi.getCsrfToken).toHaveBeenCalledTimes(callsBeforeRefresh)

    // Avancer de 1 seconde supplémentaire (14 min exactement)
    vi.advanceTimersByTime(1000)
    // Wait for pending timers only (avoid infinite loop)
    await vi.runOnlyPendingTimersAsync()

    // Auto-refresh déclenché : au moins 1 appel supplémentaire (peut être plus si plusieurs timers)
    expect(vi.mocked(authApi.getCsrfToken).mock.calls.length).toBeGreaterThan(callsBeforeRefresh)
  })

  it('ne declenche PAS de auto-refresh si utilisateur non authentifie', async () => {
    const mockToken = 'csrf-token-abc123'
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: mockToken })

    // Simuler utilisateur non authentifié
    useAuthStore.setState({ isAuthenticated: false })

    await useAuthStore.getState().fetchCsrfToken()

    // Avancer de 14 minutes
    vi.advanceTimersByTime(14 * 60 * 1000)
    await vi.runOnlyPendingTimersAsync()

    expect(authApi.getCsrfToken).toHaveBeenCalledTimes(1) // Pas de 2ème appel
  })

  it('gere les erreurs silencieusement (console.warn uniquement)', async () => {
    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.mocked(authApi.getCsrfToken).mockRejectedValue(new Error('Network error'))

    await useAuthStore.getState().fetchCsrfToken()

    expect(consoleWarnSpy).toHaveBeenCalledWith('Failed to fetch CSRF token')
    expect(useAuthStore.getState().csrfToken).toBeNull() // State inchangé

    consoleWarnSpy.mockRestore()
  })
})

describe('AuthStore — setTokens appelle fetchCsrfToken', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
    vi.clearAllTimers()
    vi.useFakeTimers()
    // Mock authApi.me pour empêcher initialize() d'interférer
    vi.mocked(authApi.me).mockRejectedValue(new Error('Not authenticated'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('appelle fetchCsrfToken automatiquement apres setTokens', async () => {
    const mockToken = 'csrf-token-xyz789'
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: mockToken })

    useAuthStore.getState().setTokens('access-token', 'refresh-token')

    // Wait for async fetchCsrfToken call (pending only, avoid infinite loop)
    await vi.runOnlyPendingTimersAsync()

    // Vérifier que getCsrfToken a été appelé au moins une fois après setTokens
    expect(authApi.getCsrfToken).toHaveBeenCalled()
    expect(useAuthStore.getState().csrfToken).toBe(mockToken)
  })
})

describe('AuthStore — logout nettoie CSRF token', () => {
  beforeEach(() => {
    resetStore()
  })

  it('nettoie le CSRF token lors du logout', () => {
    useAuthStore.setState({
      csrfToken: 'csrf-token-to-clear',
      accessToken: 'access-token',
      isAuthenticated: true,
    })

    useAuthStore.getState().logout()

    expect(useAuthStore.getState().csrfToken).toBeNull()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })
})
