import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'
import { normalizeError } from '@/errors'

const API_URL = import.meta.env.VITE_API_URL || '/api/v1'
const TENANT_ID = import.meta.env.VITE_TENANT_ID || '1'

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-Tenant-ID': TENANT_ID,
  },
})

// Request interceptor - add auth token and CSRF token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const { accessToken, csrfToken } = useAuthStore.getState()

    // Add auth token
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`
    }

    // Add CSRF token for non-safe methods
    const unsafeMethods = ['post', 'put', 'patch', 'delete']
    if (csrfToken && config.method && unsafeMethods.includes(config.method.toLowerCase())) {
      config.headers['X-CSRF-Token'] = csrfToken
    }

    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor - handle token refresh and CSRF refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // If 401 and not already retrying, try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      try {
        const refreshToken = useAuthStore.getState().refreshToken
        if (refreshToken) {
          const response = await axios.post(`${API_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          }, {
            headers: { 'X-Tenant-ID': TENANT_ID },
          })

          const { access_token, refresh_token } = response.data
          useAuthStore.getState().setTokens(access_token, refresh_token)

          originalRequest.headers.Authorization = `Bearer ${access_token}`
          // Note: setTokens appellera automatiquement fetchCsrfToken()
          return apiClient(originalRequest)
        }
      } catch {
        // Refresh failed, logout
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
    }

    // If 403 CSRF error and not already retrying, refetch CSRF and retry
    if (error.response?.status === 403 && !originalRequest._retry) {
      const errorDetail = (error.response.data as any)?.detail
      // Détecter erreur CSRF via message backend (case-insensitive)
      const isCsrfError = typeof errorDetail === 'string' &&
                          (errorDetail.toLowerCase().includes('csrf') ||
                           errorDetail.toLowerCase().includes('token'))

      if (isCsrfError) {
        originalRequest._retry = true

        try {
          await useAuthStore.getState().fetchCsrfToken()
          // Attendre que le token soit stocké dans le store
          await new Promise(resolve => setTimeout(resolve, 100))
          const csrfToken = useAuthStore.getState().csrfToken

          if (csrfToken) {
            originalRequest.headers['X-CSRF-Token'] = csrfToken
            return apiClient(originalRequest)
          }
        } catch {
          // Si refetch échoue, laisser l'erreur se propager
          console.warn('Failed to refetch CSRF token on 403 error')
        }
      }
    }

    // Normalize all errors into typed AppError subclasses
    return Promise.reject(normalizeError(error))
  }
)

export default apiClient
