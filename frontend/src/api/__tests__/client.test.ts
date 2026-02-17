/**
 * Tests unitaires pour api/client.ts
 * Vérifie les interceptors (CSRF, auth token, retry 401/403)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { apiClient } from '../client'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'

// Mock useAuthStore (accessToken, refreshToken, logout)
vi.mock('@/stores/authStore', () => ({
  useAuthStore: {
    getState: vi.fn(),
  },
}))

// Mock useUIStore (csrfToken, fetchCsrfToken)
vi.mock('@/stores/uiStore', () => ({
  useUIStore: {
    getState: vi.fn(),
  },
}))

// Mock normalizeError (pour ne pas avoir à gérer sa logique dans les tests)
vi.mock('@/errors', () => ({
  normalizeError: (error: unknown) => error,
}))

describe('API Client - Request Interceptor (CSRF)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── POST/PUT/PATCH/DELETE : ajoute X-CSRF-Token ─────────────────────
  it('ajoute X-CSRF-Token header pour POST si csrfToken existe', async () => {
    vi.mocked(useAuthStore.getState).mockReturnValue({ accessToken: 'access-token' } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({ csrfToken: 'csrf-token-abc123' } as any)

    const requestInterceptor = apiClient.interceptors.request.handlers[0]
    const config: InternalAxiosRequestConfig = {
      method: 'post',
      url: '/products',
      headers: {} as any,
    } as InternalAxiosRequestConfig

    const result = requestInterceptor.fulfilled!(config)

    expect(result.headers['X-CSRF-Token']).toBe('csrf-token-abc123')
  })

  it('ajoute X-CSRF-Token header pour PUT si csrfToken existe', async () => {
    vi.mocked(useAuthStore.getState).mockReturnValue({ accessToken: 'access-token' } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({ csrfToken: 'csrf-token-xyz' } as any)

    const requestInterceptor = apiClient.interceptors.request.handlers[0]
    const config: InternalAxiosRequestConfig = {
      method: 'put',
      url: '/products/1',
      headers: {} as any,
    } as InternalAxiosRequestConfig

    const result = requestInterceptor.fulfilled!(config)

    expect(result.headers['X-CSRF-Token']).toBe('csrf-token-xyz')
  })

  it('ajoute X-CSRF-Token header pour PATCH si csrfToken existe', async () => {
    vi.mocked(useAuthStore.getState).mockReturnValue({ accessToken: 'access-token' } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({ csrfToken: 'csrf-patch-token' } as any)

    const requestInterceptor = apiClient.interceptors.request.handlers[0]
    const config: InternalAxiosRequestConfig = {
      method: 'patch',
      url: '/products/1',
      headers: {} as any,
    } as InternalAxiosRequestConfig

    const result = requestInterceptor.fulfilled!(config)

    expect(result.headers['X-CSRF-Token']).toBe('csrf-patch-token')
  })

  it('ajoute X-CSRF-Token header pour DELETE si csrfToken existe', async () => {
    vi.mocked(useAuthStore.getState).mockReturnValue({ accessToken: 'access-token' } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({ csrfToken: 'csrf-delete-token' } as any)

    const requestInterceptor = apiClient.interceptors.request.handlers[0]
    const config: InternalAxiosRequestConfig = {
      method: 'delete',
      url: '/products/1',
      headers: {} as any,
    } as InternalAxiosRequestConfig

    const result = requestInterceptor.fulfilled!(config)

    expect(result.headers['X-CSRF-Token']).toBe('csrf-delete-token')
  })

  // ── GET : n'ajoute PAS X-CSRF-Token ─────────────────────────────────
  it('n ajoute PAS X-CSRF-Token header pour GET (safe method)', async () => {
    vi.mocked(useAuthStore.getState).mockReturnValue({ accessToken: 'access-token' } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({ csrfToken: 'csrf-token-should-not-be-added' } as any)

    const requestInterceptor = apiClient.interceptors.request.handlers[0]
    const config: InternalAxiosRequestConfig = {
      method: 'get',
      url: '/products',
      headers: {} as any,
    } as InternalAxiosRequestConfig

    const result = requestInterceptor.fulfilled!(config)

    expect(result.headers['X-CSRF-Token']).toBeUndefined()
  })

  it('n ajoute PAS X-CSRF-Token si csrfToken est null', async () => {
    vi.mocked(useAuthStore.getState).mockReturnValue({ accessToken: 'access-token' } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({ csrfToken: null } as any)

    const requestInterceptor = apiClient.interceptors.request.handlers[0]
    const config: InternalAxiosRequestConfig = {
      method: 'post',
      url: '/products',
      headers: {} as any,
    } as InternalAxiosRequestConfig

    const result = requestInterceptor.fulfilled!(config)

    expect(result.headers['X-CSRF-Token']).toBeUndefined()
  })
})

describe('API Client - Request Interceptor (Auth Token)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ajoute Authorization header si accessToken existe', async () => {
    vi.mocked(useAuthStore.getState).mockReturnValue({ accessToken: 'bearer-token-123' } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({ csrfToken: null } as any)

    const requestInterceptor = apiClient.interceptors.request.handlers[0]
    const config: InternalAxiosRequestConfig = {
      method: 'get',
      url: '/products',
      headers: {} as any,
    } as InternalAxiosRequestConfig

    const result = requestInterceptor.fulfilled!(config)

    expect(result.headers.Authorization).toBe('Bearer bearer-token-123')
  })

  it('n ajoute PAS Authorization header si accessToken est null', async () => {
    vi.mocked(useAuthStore.getState).mockReturnValue({ accessToken: null } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({ csrfToken: null } as any)

    const requestInterceptor = apiClient.interceptors.request.handlers[0]
    const config: InternalAxiosRequestConfig = {
      method: 'get',
      url: '/products',
      headers: {} as any,
    } as InternalAxiosRequestConfig

    const result = requestInterceptor.fulfilled!(config)

    expect(result.headers.Authorization).toBeUndefined()
  })
})

describe('API Client - Response Interceptor (403 CSRF Retry)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('detecte erreur 403 CSRF et refetch le token automatiquement', async () => {
    const mockFetchCsrfToken = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useAuthStore.getState).mockReturnValue({ refreshToken: null, logout: vi.fn() } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({
      fetchCsrfToken: mockFetchCsrfToken,
      csrfToken: 'new-csrf-token',
    } as any)

    const error = new AxiosError(
      'Forbidden',
      '403',
      {} as any,
      {},
      {
        status: 403,
        data: { detail: 'Invalid CSRF token' },
        statusText: 'Forbidden',
        headers: {},
        config: {
          method: 'post',
          url: '/products',
          headers: {} as any,
        } as InternalAxiosRequestConfig,
      }
    )

    const responseInterceptor = apiClient.interceptors.response.handlers[0]

    try {
      await responseInterceptor.rejected!(error)
    } catch {
      // Expected to throw après retry
    }

    expect(mockFetchCsrfToken).toHaveBeenCalledOnce()
  })

  it('detecte erreur 403 avec detail contenant "token" (case-insensitive)', async () => {
    const mockFetchCsrfToken = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useAuthStore.getState).mockReturnValue({ refreshToken: null, logout: vi.fn() } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({
      fetchCsrfToken: mockFetchCsrfToken,
      csrfToken: 'new-csrf-token',
    } as any)

    const error = new AxiosError(
      'Forbidden',
      '403',
      {} as any,
      {},
      {
        status: 403,
        data: { detail: 'Missing Token in headers' },
        statusText: 'Forbidden',
        headers: {},
        config: {
          method: 'post',
          url: '/products',
          headers: {} as any,
        } as InternalAxiosRequestConfig,
      }
    )

    const responseInterceptor = apiClient.interceptors.response.handlers[0]

    try {
      await responseInterceptor.rejected!(error)
    } catch {
      // Expected
    }

    expect(mockFetchCsrfToken).toHaveBeenCalledOnce()
  })

  it('ne retry PAS si erreur 403 n est pas liee au CSRF', async () => {
    const mockFetchCsrfToken = vi.fn()
    vi.mocked(useAuthStore.getState).mockReturnValue({ refreshToken: null, logout: vi.fn() } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({
      fetchCsrfToken: mockFetchCsrfToken,
      csrfToken: 'token',
    } as any)

    const error = new AxiosError(
      'Forbidden',
      '403',
      {} as any,
      {},
      {
        status: 403,
        data: { detail: 'Permission denied' },
        statusText: 'Forbidden',
        headers: {},
        config: {
          method: 'post',
          url: '/products',
          headers: {} as any,
        } as InternalAxiosRequestConfig,
      }
    )

    const responseInterceptor = apiClient.interceptors.response.handlers[0]

    try {
      await responseInterceptor.rejected!(error)
    } catch {
      // Expected
    }

    expect(mockFetchCsrfToken).not.toHaveBeenCalled()
  })

  it('ne retry PAS deux fois (flag _retry)', async () => {
    const mockFetchCsrfToken = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useAuthStore.getState).mockReturnValue({ refreshToken: null, logout: vi.fn() } as any)
    vi.mocked(useUIStore.getState).mockReturnValue({
      fetchCsrfToken: mockFetchCsrfToken,
      csrfToken: 'new-csrf-token',
    } as any)

    const config = {
      method: 'post',
      url: '/products',
      headers: {} as any,
      _retry: true, // Déjà retry une fois
    } as InternalAxiosRequestConfig & { _retry?: boolean }

    const error = new AxiosError(
      'Forbidden',
      '403',
      config, // ← Config ici (error.config)
      {},
      {
        status: 403,
        data: { detail: 'Invalid CSRF token' },
        statusText: 'Forbidden',
        headers: {},
        config, // ← Et aussi ici (error.response.config)
      }
    )

    const responseInterceptor = apiClient.interceptors.response.handlers[0]

    try {
      await responseInterceptor.rejected!(error)
    } catch {
      // Expected
    }

    expect(mockFetchCsrfToken).not.toHaveBeenCalled()
  })
})
