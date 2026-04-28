/**
 * massacorpClient — client HTTP dédié au backend MassaCorp.
 * Clone de fetchClient avec baseURL VITE_MASSACORP_API_URL + tokenStore MassaCorp.
 * Supporte : retry 401 refresh, retry 403 CSRF, AppError subclasses, shortcuts.
 */

import { massacorpTokenStore } from '@/stores/massacorpTokenStore'
import { generateUUID } from '@shared/utils/uuid'
import {
  AppError,
  AuthError,
  ForbiddenError,
  NetworkError,
  NotFoundError,
  ServerError,
  ValidationError,
} from '@shared/errors/types'

// ── Injection de dépendances ──────────────────────────────────────────────────

interface MassaCorpClientCallbacks {
  onTokenRefreshed: (token: string) => void
  onUnauthorized: () => void
  getCSRF: () => string | null
  fetchCSRF: () => Promise<void>
  /** Retourne le tenant_id actif (restaurant ou épicerie) pour X-Tenant-ID */
  getActiveTenantId: () => string | null
}

let _callbacks: MassaCorpClientCallbacks = {
  onTokenRefreshed: () => {},
  onUnauthorized: () => {},
  getCSRF: () => null,
  fetchCSRF: async () => {},
  getActiveTenantId: () => null,
}

export function configureMassaCorpClient(opts: MassaCorpClientCallbacks): void {
  _callbacks = opts
}

const MASSACORP_API_URL = import.meta.env.VITE_API_URL || '/api/v1'
const MASSACORP_AUTH_TENANT_ID = import.meta.env.VITE_MASSACORP_AUTH_TENANT_ID || ''

const UNSAFE_METHODS = new Set(['POST', 'PATCH', 'PUT', 'DELETE'])
const IDEMPOTENCY_METHODS = new Set(['POST', 'PATCH', 'PUT'])

// ── Types ─────────────────────────────────────────────────────────────────────

interface FetchOptions extends RequestInit {
  _retry?: boolean
}

// ── buildHeaders ──────────────────────────────────────────────────────────────

function buildHeaders(opts: {
  method: string
  isFormData?: boolean
}): Record<string, string> {
  const method = opts.method.toUpperCase()
  const headers: Record<string, string> = {}

  const token = massacorpTokenStore.getAccessToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const tenantId = _callbacks.getActiveTenantId() || MASSACORP_AUTH_TENANT_ID
  if (tenantId) {
    headers['X-Tenant-ID'] = tenantId
  }

  if (!opts.isFormData) {
    headers['Content-Type'] = 'application/json'
  }

  if (UNSAFE_METHODS.has(method)) {
    const csrf = _callbacks.getCSRF()
    if (csrf) headers['X-CSRF-Token'] = csrf
  }

  if (IDEMPOTENCY_METHODS.has(method)) {
    headers['Idempotency-Key'] = generateUUID()
  }

  return headers
}

// ── Gestion erreurs ───────────────────────────────────────────────────────────

async function extractBody(response: Response): Promise<unknown> {
  const ct = response.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    try { return await response.json() } catch { return null }
  }
  return null
}

function extractServerMessage(data: unknown): string | undefined {
  if (!data || typeof data !== 'object') return undefined
  const obj = data as Record<string, unknown>
  if (typeof obj.detail === 'string') return obj.detail
  if (typeof obj.message === 'string') return obj.message
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

// ── Refresh token ─────────────────────────────────────────────────────────────

let _refreshPromise: Promise<string> | null = null

async function _doRefresh(): Promise<string> {
  const response = await fetch(`${MASSACORP_API_URL}/auth/v2/refresh`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      // Refresh utilise toujours le tenant d'auth MassaCorp
      ...(MASSACORP_AUTH_TENANT_ID ? { 'X-Tenant-ID': MASSACORP_AUTH_TENANT_ID } : {}),
    },
    credentials: 'include',
    signal: AbortSignal.timeout(5000),
  })
  if (!response.ok) throw new AuthError('Refresh échoué.', response.status)
  const json = await response.json()
  return (json?.data?.access_token ?? json?.access_token) as string
}

export function refreshMassaCorpToken(): Promise<string> {
  if (!_refreshPromise) {
    _refreshPromise = _doRefresh().finally(() => { _refreshPromise = null })
  }
  return _refreshPromise
}

// ── Switch membership ─────────────────────────────────────────────────────────

const _switchPromises = new Map<string, Promise<string>>()

async function _doSwitchMembership(tenantId: string): Promise<string> {
  const response = await fetch(`${MASSACORP_API_URL}/auth/v2/switch-membership`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(MASSACORP_AUTH_TENANT_ID ? { 'X-Tenant-ID': MASSACORP_AUTH_TENANT_ID } : {}),
    },
    credentials: 'include',
    body: JSON.stringify({ tenant_id: Number(tenantId) }),
    signal: AbortSignal.timeout(5000),
  })
  if (!response.ok) throw new AuthError('Switch membership échoué.', response.status)
  const json = await response.json()
  return (json?.data?.access_token ?? json?.access_token) as string
}

/** Émet un access token pour le tenant cible sans rotation du refresh cookie. */
export function switchMembershipToken(tenantId: string): Promise<string> {
  const existing = _switchPromises.get(tenantId)
  if (existing) return existing
  const promise = _doSwitchMembership(tenantId).finally(() => {
    _switchPromises.delete(tenantId)
  })
  _switchPromises.set(tenantId, promise)
  return promise
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
    response = await fetch(`${MASSACORP_API_URL}${path}`, {
      ...opts,
      method,
      headers,
      credentials: 'include',
    })
  } catch {
    throw new NetworkError('Impossible de joindre le serveur MassaCorp.')
  }

  if (response.status === 401 && !opts._retry) {
    try {
      const newToken = await refreshMassaCorpToken()
      _callbacks.onTokenRefreshed(newToken)
    } catch {
      _callbacks.onUnauthorized()
      window.dispatchEvent(new CustomEvent('massacorp:session-expired'))
      throw new AuthError('Session expirée.', 401)
    }
    return _fetch<T>(path, { ...opts, _retry: true })
  }

  if (response.status === 403 && !opts._retry) {
    const data = await extractBody(response)
    const msg = extractServerMessage(data) || ''
    if (msg.toLowerCase().includes('csrf')) {
      await _callbacks.fetchCSRF()
      return _fetch<T>(path, { ...opts, _retry: true })
    }
  }

  if (!response.ok) await throwFetchError(response)
  if (response.status === 204) return undefined as T

  const json = await response.json()
  return (json?.data ?? json) as T
}

// ── API shortcuts ─────────────────────────────────────────────────────────────

export const massacorpApi = {
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

// ── fetchFormData — login (application/x-www-form-urlencoded) ─────────────────

export async function massacorpFetchFormData<T>(
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
    response = await fetch(`${MASSACORP_API_URL}${path}`, {
      method: 'POST',
      headers,
      body: params,
      credentials: 'include',
    })
  } catch {
    throw new NetworkError('Impossible de joindre le serveur MassaCorp.')
  }

  if (!response.ok) await throwFetchError(response)
  if (response.status === 204) return undefined as T
  const json = await response.json()
  return (json?.data ?? json) as T
}
