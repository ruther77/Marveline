/**
 * Tests unitaires pour stores/uiStore.ts
 * Zustand persist — testé via getState(). authApi mocké.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useUIStore } from '../uiStore'

// Mock authApi (utilisé uniquement dans fetchCsrfToken)
vi.mock('@/api/auth', () => ({
  authApi: {
    getCsrfToken: vi.fn(),
  },
}))

// Mock window.matchMedia (non disponible en jsdom par défaut)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('dark'),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

const resetUI = () =>
  useUIStore.setState({
    theme: 'dark',
    resolvedTheme: 'dark',
    sidebarState: 'expanded',
    sidebarPinned: true,
    commandPaletteOpen: false,
    searchOpen: false,
    settingsOpen: false,
    notifications: [],
    unreadCount: 0,
    compactMode: false,
    animationsEnabled: true,
    soundEnabled: true,
    globalLoading: false,
    globalLoadingMessage: null,
    csrfToken: null,
  })

beforeEach(() => {
  vi.clearAllMocks()
  resetUI()
})

// ─── Thème ────────────────────────────────────────────────────────────────────

describe('uiStore - theme', () => {
  it('thème dark par défaut', () => {
    expect(useUIStore.getState().theme).toBe('dark')
    expect(useUIStore.getState().resolvedTheme).toBe('dark')
  })

  it('setTheme passe en light', () => {
    useUIStore.getState().setTheme('light')
    expect(useUIStore.getState().theme).toBe('light')
    expect(useUIStore.getState().resolvedTheme).toBe('light')
  })

  it('toggleTheme dark → light', () => {
    useUIStore.getState().toggleTheme()
    expect(useUIStore.getState().theme).toBe('light')
  })

  it('toggleTheme light → dark', () => {
    useUIStore.getState().setTheme('light')
    useUIStore.getState().toggleTheme()
    expect(useUIStore.getState().theme).toBe('dark')
  })
})

// ─── Sidebar ─────────────────────────────────────────────────────────────────

describe('uiStore - sidebar', () => {
  it('sidebar expanded par défaut', () => {
    expect(useUIStore.getState().sidebarState).toBe('expanded')
  })

  it('toggleSidebar expanded → collapsed', () => {
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarState).toBe('collapsed')
  })

  it('toggleSidebar collapsed → expanded', () => {
    useUIStore.getState().collapseSidebar()
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarState).toBe('expanded')
  })

  it('collapseSidebar force collapsed', () => {
    useUIStore.getState().collapseSidebar()
    expect(useUIStore.getState().sidebarState).toBe('collapsed')
  })

  it('expandSidebar force expanded', () => {
    useUIStore.getState().collapseSidebar()
    useUIStore.getState().expandSidebar()
    expect(useUIStore.getState().sidebarState).toBe('expanded')
  })

  it('setSidebarPinned change le pinned', () => {
    useUIStore.getState().setSidebarPinned(false)
    expect(useUIStore.getState().sidebarPinned).toBe(false)
  })
})

// ─── Modaux ───────────────────────────────────────────────────────────────────

describe('uiStore - modaux', () => {
  it('openCommandPalette / closeCommandPalette', () => {
    useUIStore.getState().openCommandPalette()
    expect(useUIStore.getState().commandPaletteOpen).toBe(true)

    useUIStore.getState().closeCommandPalette()
    expect(useUIStore.getState().commandPaletteOpen).toBe(false)
  })

  it('toggleCommandPalette alterne', () => {
    useUIStore.getState().toggleCommandPalette()
    expect(useUIStore.getState().commandPaletteOpen).toBe(true)

    useUIStore.getState().toggleCommandPalette()
    expect(useUIStore.getState().commandPaletteOpen).toBe(false)
  })

  it('openSearch / closeSearch', () => {
    useUIStore.getState().openSearch()
    expect(useUIStore.getState().searchOpen).toBe(true)

    useUIStore.getState().closeSearch()
    expect(useUIStore.getState().searchOpen).toBe(false)
  })

  it('openSettings / closeSettings', () => {
    useUIStore.getState().openSettings()
    expect(useUIStore.getState().settingsOpen).toBe(true)

    useUIStore.getState().closeSettings()
    expect(useUIStore.getState().settingsOpen).toBe(false)
  })
})

// ─── Notifications ────────────────────────────────────────────────────────────

describe('uiStore - notifications', () => {
  it('addNotification crée une notification avec id et read=false', () => {
    useUIStore.getState().addNotification({ type: 'info', title: 'Test notif' })

    const { notifications, unreadCount } = useUIStore.getState()
    expect(notifications).toHaveLength(1)
    expect(notifications[0].read).toBe(false)
    expect(notifications[0].id).toBeTruthy()
    expect(unreadCount).toBe(1)
  })

  it('markAsRead marque la notification et décrémente unreadCount', () => {
    useUIStore.getState().addNotification({ type: 'success', title: 'Succès' })
    const id = useUIStore.getState().notifications[0].id

    useUIStore.getState().markAsRead(id)

    expect(useUIStore.getState().notifications[0].read).toBe(true)
    expect(useUIStore.getState().unreadCount).toBe(0)
  })

  it('markAsRead idempotent (double markAsRead)', () => {
    useUIStore.getState().addNotification({ type: 'warning', title: 'Attention' })
    const id = useUIStore.getState().notifications[0].id

    useUIStore.getState().markAsRead(id)
    useUIStore.getState().markAsRead(id)

    expect(useUIStore.getState().unreadCount).toBe(0)
  })

  it('markAllAsRead passe tout à read=true', () => {
    useUIStore.getState().addNotification({ type: 'info', title: 'A' })
    useUIStore.getState().addNotification({ type: 'error', title: 'B' })

    useUIStore.getState().markAllAsRead()

    const { notifications, unreadCount } = useUIStore.getState()
    expect(notifications.every((n) => n.read)).toBe(true)
    expect(unreadCount).toBe(0)
  })

  it('removeNotification supprime et décrémente si non lue', () => {
    useUIStore.getState().addNotification({ type: 'info', title: 'X' })
    const id = useUIStore.getState().notifications[0].id

    useUIStore.getState().removeNotification(id)

    expect(useUIStore.getState().notifications).toHaveLength(0)
    expect(useUIStore.getState().unreadCount).toBe(0)
  })

  it('removeNotification ne décrémente pas si déjà lue', () => {
    useUIStore.getState().addNotification({ type: 'info', title: 'Y' })
    const id = useUIStore.getState().notifications[0].id
    useUIStore.getState().markAsRead(id) // unreadCount = 0

    useUIStore.getState().removeNotification(id)

    expect(useUIStore.getState().unreadCount).toBe(0) // pas -1
  })

  it('clearNotifications vide tout', () => {
    useUIStore.getState().addNotification({ type: 'info', title: 'A' })
    useUIStore.getState().addNotification({ type: 'info', title: 'B' })

    useUIStore.getState().clearNotifications()

    expect(useUIStore.getState().notifications).toHaveLength(0)
    expect(useUIStore.getState().unreadCount).toBe(0)
  })
})

// ─── Préférences ──────────────────────────────────────────────────────────────

describe('uiStore - préférences', () => {
  it('setCompactMode passe à true', () => {
    useUIStore.getState().setCompactMode(true)
    expect(useUIStore.getState().compactMode).toBe(true)
  })

  it('setAnimationsEnabled passe à false', () => {
    useUIStore.getState().setAnimationsEnabled(false)
    expect(useUIStore.getState().animationsEnabled).toBe(false)
  })

  it('setSoundEnabled passe à false', () => {
    useUIStore.getState().setSoundEnabled(false)
    expect(useUIStore.getState().soundEnabled).toBe(false)
  })
})

// ─── Global loading ───────────────────────────────────────────────────────────

describe('uiStore - globalLoading', () => {
  it('setGlobalLoading(true, message) active le loading', () => {
    useUIStore.getState().setGlobalLoading(true, 'Chargement...')
    expect(useUIStore.getState().globalLoading).toBe(true)
    expect(useUIStore.getState().globalLoadingMessage).toBe('Chargement...')
  })

  it('setGlobalLoading(false) désactive sans message', () => {
    useUIStore.getState().setGlobalLoading(true, 'test')
    useUIStore.getState().setGlobalLoading(false)
    expect(useUIStore.getState().globalLoading).toBe(false)
    expect(useUIStore.getState().globalLoadingMessage).toBeNull()
  })
})

// ─── CSRF ─────────────────────────────────────────────────────────────────────

describe('uiStore - CSRF token', () => {
  it('setCsrfToken stocke le token', () => {
    useUIStore.getState().setCsrfToken('csrf-abc123')
    expect(useUIStore.getState().csrfToken).toBe('csrf-abc123')
  })

  it('clearCsrfToken remet à null', () => {
    useUIStore.getState().setCsrfToken('csrf-abc123')
    useUIStore.getState().clearCsrfToken()
    expect(useUIStore.getState().csrfToken).toBeNull()
  })

  it('fetchCsrfToken appelle authApi.getCsrfToken et stocke le token', async () => {
    const { authApi } = await import('@/api/auth')
    vi.mocked(authApi.getCsrfToken).mockResolvedValue({ csrf_token: 'csrf-from-server' })

    await useUIStore.getState().fetchCsrfToken()

    expect(authApi.getCsrfToken).toHaveBeenCalledOnce()
    expect(useUIStore.getState().csrfToken).toBe('csrf-from-server')
  })

  it('fetchCsrfToken ne crash pas si authApi échoue', async () => {
    const { authApi } = await import('@/api/auth')
    vi.mocked(authApi.getCsrfToken).mockRejectedValue(new Error('network error'))

    // Ne doit pas rejeter (erreur silencieuse intentionnelle)
    await expect(useUIStore.getState().fetchCsrfToken()).resolves.toBeUndefined()
  })
})
