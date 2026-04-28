/**
 * Tests unitaires pour stores/authStore.ts
 *
 * Architecture actuelle :
 *   - accessToken → tokenStore (in-memory, jamais dans Zustand)
 *   - CSRF token  → useUIStore (géré par fetchCsrfToken / clearCsrfToken)
 *   - refreshToken → httpOnly cookie backend (invisible côté JS)
 *   - persist partiel : { isAuthenticated } — mfaSessionToken exclu (NC-08, mémoire seulement)
 *
 * Mocks : authApi (me, getCsrfToken), configureApiClient (side-effect module)
 * Réel  : tokenStore, useUIStore (authApi.getCsrfToken mocké → fetchCsrfToken OK)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ── Mocks (hoistés avant les imports) ────────────────────────────────────────

vi.mock('@/api/auth', () => ({
  authApi: {
    me: vi.fn(),
    getCsrfToken: vi.fn(),
  },
}))

vi.mock('@/api/users', () => ({
  usersApi: {
    getMyProfile: vi.fn(),
  },
}))

// configureApiClient est appelé au niveau module lors du chargement de authStore
vi.mock('@/api/fetchClient', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
  fetchBlob: vi.fn(),
  fetchFormData: vi.fn(),
  configureApiClient: vi.fn(),
  refreshAccessToken: vi.fn().mockResolvedValue('refreshed-token'),
}))

// ── Imports (après les mocks) ─────────────────────────────────────────────────

import { useAuthStore } from '../authStore'
import { tokenStore } from '../tokenStore'
import { useUIStore } from '../uiStore'
import { authApi } from '@/api/auth'
import { usersApi } from '@/api/users'
import type { User } from '@/types'

// ── Fixtures ──────────────────────────────────────────────────────────────────

const mockUser: User = {
  id: 1,
  email: 'test@marveline.com',
  full_name: 'Jean Dupont',
  first_name: 'Jean',
  last_name: 'Dupont',
  role: 'staff',
  tenant_id: 1,
  is_active: true,
  permissions: [],
  created_at: '2026-01-01T00:00:00Z',
}

// ── Reset complet avant chaque test ──────────────────────────────────────────

function resetAll() {
  tokenStore.clear()
  useAuthStore.setState({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    mfaSessionToken: null,
  })
  useUIStore.setState({ csrfToken: null })
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(usersApi.getMyProfile).mockResolvedValue(mockUser)
  resetAll()
})

// ─── État initial ─────────────────────────────────────────────────────────────

describe('authStore - état initial', () => {
  it('user null, non authentifié, pas de MFA token', () => {
    const { user, isAuthenticated, mfaSessionToken } = useAuthStore.getState()
    expect(user).toBeNull()
    expect(isAuthenticated).toBe(false)
    expect(mfaSessionToken).toBeNull()
  })

  it('tokenStore vide au départ', () => {
    expect(tokenStore.getAccessToken()).toBeNull()
  })
})

// ─── setTokens ────────────────────────────────────────────────────────────────

describe('authStore - setTokens', () => {
  it('stocke le token dans tokenStore (pas dans Zustand)', () => {
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: 'csrf-123' })

    useAuthStore.getState().setTokens('eyJ.test.token')

    expect(tokenStore.getAccessToken()).toBe('eyJ.test.token')
    // Le token n'est PAS dans l'état Zustand (séparation intentionnelle)
    expect((useAuthStore.getState() as any).accessToken).toBeUndefined()
  })

  it('passe isAuthenticated à true', () => {
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: 'csrf-123' })

    useAuthStore.getState().setTokens('my-token')

    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })

  it('ne déclenche plus fetchCsrfToken (géré par initialize)', () => {
    useAuthStore.getState().setTokens('my-token')

    // CSRF est désormais géré par initialize(), pas par setTokens
    expect(useUIStore.getState().csrfToken).toBeNull()
  })
})

// ─── setUser ──────────────────────────────────────────────────────────────────

describe('authStore - setUser', () => {
  it('stocke le user dans l\'état', () => {
    useAuthStore.getState().setUser(mockUser)
    expect(useAuthStore.getState().user).toEqual(mockUser)
  })

  it('remplace l\'ancien user', () => {
    useAuthStore.getState().setUser(mockUser)
    useAuthStore.getState().setUser({ ...mockUser, first_name: 'Marie' })
    expect(useAuthStore.getState().user?.first_name).toBe('Marie')
  })
})

// ─── setMfaSessionToken ───────────────────────────────────────────────────────

describe('authStore - setMfaSessionToken', () => {
  it('stocke le token MFA', () => {
    useAuthStore.getState().setMfaSessionToken('mfa-session-abc')
    expect(useAuthStore.getState().mfaSessionToken).toBe('mfa-session-abc')
  })
})

// ─── logout ───────────────────────────────────────────────────────────────────

describe('authStore - logout', () => {
  beforeEach(() => {
    // Préparer un état authentifié
    tokenStore.setAccessToken('valid-token')
    useUIStore.setState({ csrfToken: 'csrf-active' })
    useAuthStore.setState({
      user: mockUser,
      isAuthenticated: true,
      mfaSessionToken: 'mfa-token',
    })
  })

  it('efface le tokenStore', () => {
    useAuthStore.getState().logout()
    expect(tokenStore.getAccessToken()).toBeNull()
  })

  it('remet user, isAuthenticated, mfaSessionToken à zéro', () => {
    useAuthStore.getState().logout()
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.isAuthenticated).toBe(false)
    expect(state.mfaSessionToken).toBeNull()
  })

  it('efface le CSRF token dans uiStore', () => {
    useAuthStore.getState().logout()
    expect(useUIStore.getState().csrfToken).toBeNull()
  })
})

// ─── fetchUser ────────────────────────────────────────────────────────────────

describe('authStore - fetchUser', () => {
  it('stocke le user en cas de succès', async () => {
    vi.mocked(authApi.me).mockResolvedValue(mockUser)
    vi.mocked(usersApi.getMyProfile).mockResolvedValue(mockUser)

    await useAuthStore.getState().fetchUser()

    expect(useAuthStore.getState().user).toEqual(mockUser)
  })

  it('fusionne auth/me + users/me et garde role/permissions de auth/me', async () => {
    const authUser: User = {
      ...mockUser,
      first_name: 'AuthFirst',
      role: 'tenant_admin',
      permissions: ['users:read'],
    }
    const profileUser: User = {
      ...mockUser,
      first_name: 'ProfileFirst',
      role: 'staff',
      permissions: ['should-not-win'],
    }
    vi.mocked(authApi.me).mockResolvedValue(authUser)
    vi.mocked(usersApi.getMyProfile).mockResolvedValue(profileUser)

    await useAuthStore.getState().fetchUser()

    expect(useAuthStore.getState().user).toMatchObject({
      first_name: 'ProfileFirst',
      role: 'tenant_admin',
      permissions: ['users:read'],
    })
  })

  it('retombe sur auth/me si users/me échoue', async () => {
    const authUser: User = {
      ...mockUser,
      role: 'admin',
      permissions: ['profile:read'],
    }
    vi.mocked(authApi.me).mockResolvedValue(authUser)
    vi.mocked(usersApi.getMyProfile).mockRejectedValue(new Error('users/me unavailable'))

    await useAuthStore.getState().fetchUser()

    expect(useAuthStore.getState().user).toEqual(authUser)
  })

  it('garde l\'état user si authApi.me échoue (erreur réseau)', async () => {
    tokenStore.setAccessToken('expired-token')
    useAuthStore.setState({ isAuthenticated: true, user: mockUser })
    vi.mocked(authApi.me).mockRejectedValue(new Error('401 Unauthorized'))

    await useAuthStore.getState().fetchUser()

    // fetchUser ne force plus le logout — erreur gérée par fetchClient.onUnauthorized
    expect(useAuthStore.getState().user).toEqual(mockUser)
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })
})

// ─── initialize ───────────────────────────────────────────────────────────────

describe('authStore - initialize', () => {
  // Pré-charger un token pour éviter la branche refreshAccessToken (dynamic import)
  // qui cause des timeouts dans le contexte vitest + vi.mock
  beforeEach(() => {
    tokenStore.setAccessToken('existing-token')
  })

  it('succès : user, isAuthenticated=true, isLoading=false', async () => {
    vi.mocked(authApi.me).mockResolvedValue(mockUser)
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: 'csrf-init' })

    await useAuthStore.getState().initialize()

    const state = useAuthStore.getState()
    expect(state.user).toEqual(mockUser)
    expect(state.isAuthenticated).toBe(true)
    expect(state.isLoading).toBe(false)
  })

  it('échec (401) : logout + isLoading=false', async () => {
    vi.mocked(authApi.me).mockRejectedValue(new Error('401'))
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: 'csrf' })

    await useAuthStore.getState().initialize()

    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.isAuthenticated).toBe(false)
    expect(state.isLoading).toBe(false)
  })

  it('timeout (5s) : logout + isLoading=false', async () => {
    vi.useFakeTimers()
    // authApi.me ne se résout jamais (simule un timeout réseau)
    vi.mocked(authApi.me).mockImplementation(
      () => new Promise(() => {}) // jamais resolue
    )
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: 'csrf' })

    const initPromise = useAuthStore.getState().initialize()

    // Avancer de 5001ms pour dépasser le timeout
    vi.advanceTimersByTime(5001)
    await initPromise

    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.isAuthenticated).toBe(false)
    expect(state.isLoading).toBe(false)

    vi.useRealTimers()
  })
})

describe('authStore - initialize deduplication', () => {
  // Pré-charger un token pour éviter la branche refreshAccessToken (dynamic import)
  beforeEach(() => {
    tokenStore.setAccessToken('existing-token')
  })

  it('deux appels concurrents ne déclenchent authApi.me qu\'une seule fois', async () => {
    vi.mocked(authApi.me).mockResolvedValue(mockUser)
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: 'csrf' })

    // Lancer deux fois en parallèle
    const p1 = useAuthStore.getState().initialize()
    const p2 = useAuthStore.getState().initialize()

    await Promise.all([p1, p2])

    // authApi.me ne doit être appelé qu'une seule fois (deduplication)
    expect(authApi.me).toHaveBeenCalledTimes(1)
  })

  it('après résolution, un second initialize() repart from scratch', async () => {
    vi.mocked(authApi.me).mockResolvedValue(mockUser)
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: 'csrf' })

    await useAuthStore.getState().initialize()
    vi.mocked(authApi.me).mockClear()

    // Forcer user=null pour invalider le cache 30s (_initCacheExpiry)
    // Le cache ne skip que si isAuthenticated && user sont truthy
    useAuthStore.setState({ user: null })

    await useAuthStore.getState().initialize()

    // Second appel (cache invalidé par user=null) → nouvel appel à me()
    expect(authApi.me).toHaveBeenCalledTimes(1)
  })
})

// ─── Persistance ──────────────────────────────────────────────────────────────

describe('authStore - persist config', () => {
  it('la clé de stockage est "marveline-auth"', () => {
    // Vérification via localStorage après une action qui déclenche la persist
    useAuthStore.setState({ isAuthenticated: true })
    const stored = localStorage.getItem('marveline-auth')
    expect(stored).not.toBeNull()
    const parsed = JSON.parse(stored!)
    expect(parsed.state?.isAuthenticated).toBe(true)
  })

  it('partialize : seul isAuthenticated est persisté — mfaSessionToken reste en mémoire (NC-08)', () => {
    useAuthStore.setState({
      isAuthenticated: true,
      mfaSessionToken: 'mfa-abc',
      user: mockUser,   // ne doit PAS être persisté
      isLoading: true,  // ne doit PAS être persisté
    })
    const stored = JSON.parse(localStorage.getItem('marveline-auth') || '{}')
    expect(stored.state?.isAuthenticated).toBe(true)
    expect(stored.state?.mfaSessionToken).toBeUndefined()  // mémoire uniquement (NC-08)
    expect(stored.state?.user).toBeUndefined()  // non persisté
    expect(stored.state?.isLoading).toBeUndefined() // non persisté
  })
})
