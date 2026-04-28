import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthError, NetworkError } from '@shared/errors/types'
import { createTestQueryClient } from '@/test/test-utils'
import {
  canPollNotifications,
  shouldRetryNotifications,
  useNotifications,
} from '../useNotifications'

const authState = {
  isAuthenticated: false,
  user: null as null | { id: number },
}

const listMock = vi.fn()

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (state: typeof authState) => unknown) => selector(authState),
}))

vi.mock('../../notifications', () => ({
  notificationsApi: {
    list: (...args: unknown[]) => listMock(...args),
  },
}))

function createWrapper() {
  const queryClient = createTestQueryClient()

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useNotifications', () => {
  beforeEach(() => {
    authState.isAuthenticated = false
    authState.user = null
    listMock.mockReset()
  })

  it('désactive le polling hors session authentifiée', async () => {
    const wrapper = createWrapper()

    renderHook(() => useNotifications(), { wrapper })

    await waitFor(() => {
      expect(listMock).not.toHaveBeenCalled()
    })
  })

  it('charge les notifications une fois la session disponible', async () => {
    authState.isAuthenticated = true
    authState.user = { id: 1 }
    listMock.mockResolvedValue({ items: [], total: 0, unread_count: 0 })
    const wrapper = createWrapper()

    renderHook(() => useNotifications(), { wrapper })

    await waitFor(() => {
      expect(listMock).toHaveBeenCalledTimes(1)
    })
  })

  it('ne retry pas sur erreur d’authentification', async () => {
    authState.isAuthenticated = true
    authState.user = { id: 1 }
    listMock.mockRejectedValue(new AuthError('Session expirée.', 401))
    const wrapper = createWrapper()

    const { result } = renderHook(() => useNotifications(), { wrapper })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(listMock).toHaveBeenCalledTimes(1)
  })
})

describe('notifications polling helpers', () => {
  it('autorise le polling uniquement avec session et user chargés', () => {
    expect(canPollNotifications(true, true)).toBe(true)
    expect(canPollNotifications(true, false)).toBe(false)
    expect(canPollNotifications(false, true)).toBe(false)
  })

  it('autorise un seul retry sur erreur réseau mais aucun sur auth/forbidden', () => {
    expect(shouldRetryNotifications(0, new NetworkError('offline'))).toBe(true)
    expect(shouldRetryNotifications(1, new NetworkError('offline'))).toBe(false)
    expect(shouldRetryNotifications(0, new AuthError('Session expirée.', 401))).toBe(false)
  })
})
