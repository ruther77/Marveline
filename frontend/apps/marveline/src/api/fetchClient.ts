/**
 * fetchClient — client HTTP natif (fetch API), zéro dépendance Axios.
 * Remplacera apiClient (Axios) lors de la migration S5.
 *
 * Fonctionnalités :
 * - buildHeaders() : fonction pure, testable unitairement
 * - Retry 401 → refreshAccessToken() avec flag anti-boucle
 * - Retry 403 CSRF → uiStore.fetchCsrfToken()
 * - Envelope unwrap : json?.data ?? json
 * - 204 → undefined
 * - Throw AppError subclasses (compatibles avec normalizeError)
 * - Shortcuts : api.get / api.post / api.patch / api.put / api.delete
 * - fetchBlob() pour PDF
 * - fetchFormData() pour login OAuth (application/x-www-form-urlencoded)
 */

import { tokenStore } from '@/stores/tokenStore'
import { generateUUID } from '@/utils/uuid'
import {
  AppError,
  AuthError,
  ForbiddenError,
  NetworkError,
  NotFoundError,
  ServerError,
  ValidationError,
} from '@shared/errors/types'

// ── Injection de dépendances (évite cycle fetchClient ↔ authStore/uiStore) ────

interface ApiClientCallbacks {
  onTokenRefreshed: (token: string) => void
  onUnauthorized: () => void
  getCSRF: () => string | null
  fetchCSRF: () => Promise<void>
}

let _callbacks: ApiClientCallbacks = {
  onTokenRefreshed: () => {},
  onUnauthorized: () => {},
  getCSRF: () => null,
  fetchCSRF: async () => {},
}

export function configureApiClient(opts: ApiClientCallbacks): void {
  _callbacks = opts
}

import { BRAND } from '@/brand/select'

const API_URL = import.meta.env.VITE_API_URL || '/api/v1'
const TENANT_ID = String(import.meta.env.VITE_TENANT_ID || BRAND.defaultTenantId)

const UNSAFE_METHODS = new Set(['POST', 'PATCH', 'PUT', 'DELETE'])
const IDEMPOTENCY_METHODS = new Set(['POST', 'PATCH', 'PUT'])

// ── Types ─────────────────────────────────────────────────────────────────────

interface FetchOptions extends RequestInit {
  _retry?: boolean
}

interface BuildHeadersOptions {
  method: string
  isFormData?: boolean
}

// ── buildHeaders — fonction pure, testable ────────────────────────────────────

export function buildHeaders(opts: BuildHeadersOptions): Record<string, string> {
  const method = opts.method.toUpperCase()
  const headers: Record<string, string> = {
    'X-Tenant-ID': TENANT_ID,
    'X-App-Code': 'marveline',  // ISO-APP-01
  }

  const token = tokenStore.getAccessToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  if (!opts.isFormData) {
    headers['Content-Type'] = 'application/json'
  }

  if (UNSAFE_METHODS.has(method)) {
    const csrfToken = _callbacks.getCSRF()
    if (csrfToken) {
      headers['X-CSRF-Token'] = csrfToken
    }
  }

  if (IDEMPOTENCY_METHODS.has(method)) {
    headers['Idempotency-Key'] = generateUUID()
  }

  return headers
}

// ── Gestion erreurs fetch ─────────────────────────────────────────────────────

async function extractBody(response: Response): Promise<unknown> {
  const ct = response.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    try {
      return await response.json()
    } catch {
      return null
    }
  }
  return null
}

function extractServerMessage(data: unknown): string | undefined {
  if (!data || typeof data !== 'object') return undefined
  const obj = data as Record<string, unknown>
  if (typeof obj.detail === 'string') return obj.detail
  if (typeof obj.message === 'string') return obj.message
  // Backend detail as object: { detail: { message: "...", delay_seconds: N, ... } }
  if (obj.detail !== null && typeof obj.detail === 'object' && !Array.isArray(obj.detail)) {
    const d = obj.detail as Record<string, unknown>
    if (typeof d.message === 'string') return d.message
  }
  if (Array.isArray(obj.detail)) {
    return obj.detail
      .map((e: Record<string, unknown>) => e.msg || String(e))
      .join('. ')
  }
  return undefined
}

function extractFieldErrors(data: unknown): Record<string, string[]> {
  if (!data || typeof data !== 'object') return {}
  const obj = data as Record<string, unknown>
  if (!Array.isArray(obj.detail)) return {}
  const fields: Record<string, string[]> = {}
  for (const err of obj.detail) {
    const loc = (err as Record<string, unknown>).loc as unknown[]
    const msg = String((err as Record<string, unknown>).msg || '')
    const fieldName = loc?.length > 1 ? String(loc[loc.length - 1]) : 'general'
    if (!fields[fieldName]) fields[fieldName] = []
    fields[fieldName].push(msg)
  }
  return fields
}

async function throwFetchError(response: Response): Promise<never> {
  const data = await extractBody(response)
  const msg = extractServerMessage(data)
  const { status } = response

  if (status === 401) throw new AuthError(msg || 'Session expirée.', status)
  if (status === 403) throw new ForbiddenError(msg || 'Accès refusé.')
  if (status === 404) throw new NotFoundError(msg || 'Ressource introuvable.')
  if (status === 422 || status === 400 || status === 409) {
    throw new ValidationError(
      msg || 'Données invalides.',
      status === 422 ? extractFieldErrors(data) : {},
      data,
    )
  }
  if (status === 429) throw new NetworkError('Trop de requêtes. Patientez quelques instants.')
  if (status >= 500) throw new ServerError(msg || 'Erreur interne du serveur.', status)

  throw new AppError({
    message: msg || `Erreur HTTP ${status}`,
    category: 'unknown',
    status,
    retryable: false,
  })
}

// ── Refresh token — promise partagée (anti-race) ──────────────────────────────

let _refreshPromise: Promise<string> | null = null

async function _doRefresh(): Promise<string> {
  // AbortSignal.timeout() garantit que le refresh ne reste pas en attente indéfiniment
  // si le serveur est down — évite une promise jamais résolue qui bloquerait les retry.
  const response = await fetch(`${API_URL}/auth/v2/refresh`, {
    method: 'POST',
    headers: { 'X-Tenant-ID': TENANT_ID, 'X-App-Code': 'marveline', 'Content-Type': 'application/json' },
    credentials: 'include', // httpOnly cookie refreshToken (S4)
    signal: AbortSignal.timeout(5000),
  })
  if (!response.ok) throw new AuthError('Refresh échoué.', response.status)
  const json = await response.json()
  return (json?.data?.access_token ?? json?.access_token) as string
}

export function refreshAccessToken(): Promise<string> {
  if (!_refreshPromise) {
    _refreshPromise = _doRefresh().finally(() => { _refreshPromise = null })
  }
  return _refreshPromise
}

// ── Cœur fetch ────────────────────────────────────────────────────────────────

async function _fetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const method = (opts.method || 'GET').toUpperCase()
  const isFormData = opts.body instanceof URLSearchParams || opts.body instanceof FormData

  const headers = {
    ...buildHeaders({ method, isFormData }),
    ...(opts.headers as Record<string, string> | undefined),
  }

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...opts,
      method,
      headers,
      credentials: 'include',
    })
  } catch {
    throw new NetworkError('Impossible de joindre le serveur.')
  }

  // Retry 401 — token expiré (toutes les requêtes simultanées partagent le même refresh)
  if (response.status === 401 && !opts._retry) {
    try {
      const newToken = await refreshAccessToken()
      _callbacks.onTokenRefreshed(newToken)
    } catch {
      _callbacks.onUnauthorized()
      // Dispatch event — le router réagit via beforeLoad sans hard reload
      window.dispatchEvent(new CustomEvent('auth:session-expired'))
      throw new AuthError('Session expirée.', 401)
    }
    return _fetch<T>(path, { ...opts, _retry: true })
  }

  // Retry 403 CSRF
  if (response.status === 403 && !opts._retry) {
    const data = await extractBody(response)
    const msg = extractServerMessage(data) || ''
    const isCsrf = msg.toLowerCase().includes('csrf')
    if (isCsrf) {
      await _callbacks.fetchCSRF()
      return _fetch<T>(path, { ...opts, _retry: true })
    }
  }

  if (!response.ok) await throwFetchError(response)

  // 204 No Content
  if (response.status === 204) return undefined as T

  const json = await response.json()
  return (json?.data ?? json) as T
}

// ── API shortcuts ─────────────────────────────────────────────────────────────

export const api = {
  get: <T>(path: string, opts?: FetchOptions) =>
    _fetch<T>(path, { ...opts, method: 'GET' }),

  post: <T>(path: string, body?: unknown, opts?: FetchOptions) =>
    _fetch<T>(path, {
      ...opts,
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(path: string, body?: unknown, opts?: FetchOptions) =>
    _fetch<T>(path, {
      ...opts,
      method: 'PATCH',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  put: <T>(path: string, body?: unknown, opts?: FetchOptions) =>
    _fetch<T>(path, {
      ...opts,
      method: 'PUT',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(path: string, opts?: FetchOptions) =>
    _fetch<T>(path, { ...opts, method: 'DELETE' }),
}

// ── fetchBlob — téléchargement PDF ────────────────────────────────────────────

export async function fetchBlob(path: string, opts?: FetchOptions): Promise<Blob> {
  const method = (opts?.method || 'GET').toUpperCase()
  const headers = {
    ...buildHeaders({ method }),
    Accept: 'application/pdf',
    ...(opts?.headers as Record<string, string> | undefined),
  }

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...opts,
      method,
      headers,
      credentials: 'include',
    })
  } catch {
    throw new NetworkError('Impossible de joindre le serveur.')
  }

  if (!response.ok) await throwFetchError(response)
  return response.blob()
}

// ── fetchFormData — login OAuth (application/x-www-form-urlencoded) ───────────

export async function fetchFormData<T>(
  path: string,
  body: Record<string, string>,
  extraHeaders?: Record<string, string>,
): Promise<T> {
  const params = new URLSearchParams(body)
  const headers = {
    ...buildHeaders({ method: 'POST', isFormData: true }),
    'Content-Type': 'application/x-www-form-urlencoded',
    ...extraHeaders,
  }

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers,
      body: params,
      credentials: 'include',
    })
  } catch {
    throw new NetworkError('Impossible de joindre le serveur.')
  }

  if (!response.ok) await throwFetchError(response)
  if (response.status === 204) return undefined as T
  const json = await response.json()
  return (json?.data ?? json) as T
}
