/**
 * createApiClient — factory client HTTP paramétrable par app.
 *
 * Remplace fetchClient (Marveline) et massacorpClient (MassaCorp)
 * par un seul code avec injection de config (tenantId, tokenStore, callbacks).
 *
 * Usage :
 *   const api = createApiClient({
 *     tenantId: '1',
 *     getAccessToken: () => tokenStore.getAccessToken(),
 *     ...callbacks
 *   })
 *   const products = await api.get<Product[]>('/products')
 */

import {
  AppError,
  AuthError,
  ForbiddenError,
  NetworkError,
  NotFoundError,
  ServerError,
  ValidationError,
} from '../errors/types'
import { generateUUID } from '../utils/uuid'

// ── Config & Callbacks ───────────────────────────────────────────────────────

export interface ApiClientConfig {
  apiUrl?: string
  /** Tenant ID statique (Marveline) — ignoré si getActiveTenantId fourni */
  tenantId?: string
  /** Tenant ID dynamique (MassaCorp) — prioritaire sur tenantId */
  getActiveTenantId?: () => string
  /** Tenant ID pour les endpoints auth (refresh, switch) — fallback sur tenantId */
  authTenantId?: string
  /**
   * ISO-APP-01 : code de l'app d'origine ('marveline' | 'epicerie' | 'restaurant').
   * Injecté dans le header `X-App-Code` de chaque requête, permet au backend
   * de vérifier que le JWT utilisé correspond bien à l'app.
   * Pour MassaCorp, peut être une fonction (dépend de activeTenant).
   */
  appCode?: string
  getActiveAppCode?: () => string
  getAccessToken: () => string | null
  getCsrfToken: () => string | null
  fetchCsrfToken: () => Promise<void>
  onTokenRefreshed: (token: string) => void
  onUnauthorized: () => void
  generateUUID?: () => string
  /** Nom du CustomEvent émis sur session expirée (default: 'auth:session-expired') */
  sessionExpiredEvent?: string
}

interface FetchOptions extends RequestInit {
  _retry?: boolean
}

interface BuildHeadersOptions {
  method: string
  isFormData?: boolean
}

const UNSAFE_METHODS = new Set(['POST', 'PATCH', 'PUT', 'DELETE'])
const IDEMPOTENCY_METHODS = new Set(['POST', 'PATCH', 'PUT'])

// ── Error extraction (identique fetchClient, pas de duplication) ─────────────

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

// ── Factory ──────────────────────────────────────────────────────────────────

export function createApiClient(config: ApiClientConfig) {
  const {
    apiUrl = '/api/v1',
    tenantId: staticTenantId,
    getActiveTenantId,
    authTenantId,
    appCode: staticAppCode,
    getActiveAppCode,
    getAccessToken,
    getCsrfToken,
    fetchCsrfToken,
    onTokenRefreshed,
    onUnauthorized,
    generateUUID: genUUID = generateUUID,
    sessionExpiredEvent = 'auth:session-expired',
  } = config

  function resolveTenantId(): string {
    return getActiveTenantId?.() || staticTenantId || ''
  }

  function resolveAuthTenantId(): string {
    return authTenantId || resolveTenantId()
  }

  function resolveAppCode(): string {
    return getActiveAppCode?.() || staticAppCode || ''
  }

  let _refreshPromise: Promise<string> | null = null

  function buildHeaders(opts: BuildHeadersOptions): Record<string, string> {
    const method = opts.method.toUpperCase()
    const tid = resolveTenantId()
    const appCode = resolveAppCode()
    const headers: Record<string, string> = {}
    if (tid) headers['X-Tenant-ID'] = tid
    if (appCode) headers['X-App-Code'] = appCode

    const token = getAccessToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    if (!opts.isFormData) {
      headers['Content-Type'] = 'application/json'
    }

    if (UNSAFE_METHODS.has(method)) {
      const csrfToken = getCsrfToken()
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken
      }
    }

    if (IDEMPOTENCY_METHODS.has(method)) {
      headers['Idempotency-Key'] = genUUID()
    }

    return headers
  }

  async function _doRefresh(): Promise<string> {
    const authTid = resolveAuthTenantId()
    const appCode = resolveAppCode()
    const response = await fetch(`${apiUrl}/auth/v2/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authTid ? { 'X-Tenant-ID': authTid } : {}),
        ...(appCode ? { 'X-App-Code': appCode } : {}),
      },
      credentials: 'include',
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw new AuthError('Refresh échoué.', response.status)
    const json = await response.json()
    return (json?.data?.access_token ?? json?.access_token) as string
  }

  function refreshAccessToken(): Promise<string> {
    if (!_refreshPromise) {
      _refreshPromise = _doRefresh().finally(() => {
        // Cooldown 5s : empêche un second refresh pendant que les retries
        // s'exécutent (sinon le refresh token roté cause TOKEN_REPLAY_DETECTED)
        setTimeout(() => { _refreshPromise = null }, 5000)
      })
    }
    return _refreshPromise
  }

  // ── Switch membership (MassaCorp : nouvel access token sans rotation cookie) ──

  const _switchPromises = new Map<string, Promise<string>>()

  async function _doSwitchMembership(targetTenantId: string): Promise<string> {
    const authTid = resolveAuthTenantId()
    const appCode = resolveAppCode()
    const response = await fetch(`${apiUrl}/auth/v2/switch-membership`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authTid ? { 'X-Tenant-ID': authTid } : {}),
        ...(appCode ? { 'X-App-Code': appCode } : {}),
      },
      credentials: 'include',
      body: JSON.stringify({ tenant_id: Number(targetTenantId) }),
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw new AuthError('Switch membership échoué.', response.status)
    const json = await response.json()
    return (json?.data?.access_token ?? json?.access_token) as string
  }

  function switchMembershipToken(targetTenantId: string): Promise<string> {
    const existing = _switchPromises.get(targetTenantId)
    if (existing) return existing
    const promise = _doSwitchMembership(targetTenantId).finally(() => {
      _switchPromises.delete(targetTenantId)
    })
    _switchPromises.set(targetTenantId, promise)
    return promise
  }

  async function _fetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
    const method = (opts.method || 'GET').toUpperCase()
    const isFormData = opts.body instanceof URLSearchParams || opts.body instanceof FormData

    const headers = {
      ...buildHeaders({ method, isFormData }),
      ...(opts.headers as Record<string, string> | undefined),
    }

    let response: Response
    try {
      response = await fetch(`${apiUrl}${path}`, {
        ...opts,
        method,
        headers,
        credentials: 'include',
      })
    } catch {
      throw new NetworkError('Impossible de joindre le serveur.')
    }

    if (response.status === 401 && !opts._retry) {
      try {
        const newToken = await refreshAccessToken()
        onTokenRefreshed(newToken)
      } catch {
        onUnauthorized()
        window.dispatchEvent(new CustomEvent(sessionExpiredEvent))
        throw new AuthError('Session expirée.', 401)
      }
      return _fetch<T>(path, { ...opts, _retry: true })
    }

    if (response.status === 403 && !opts._retry) {
      const data = await extractBody(response)
      const msg = extractServerMessage(data) || ''
      if (msg.toLowerCase().includes('csrf')) {
        await fetchCsrfToken()
        return _fetch<T>(path, { ...opts, _retry: true })
      }
    }

    if (!response.ok) await throwFetchError(response)
    if (response.status === 204) return undefined as T

    const json = await response.json()
    return (json?.data ?? json) as T
  }

  // ── API shortcuts ────────────────────────────────────────────────────────

  const api = {
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

  // ── fetchBlob ────────────────────────────────────────────────────────────

  async function fetchBlob(path: string, opts?: FetchOptions): Promise<Blob> {
    const method = (opts?.method || 'GET').toUpperCase()
    const headers = {
      ...buildHeaders({ method }),
      Accept: 'application/pdf',
      ...(opts?.headers as Record<string, string> | undefined),
    }

    let response: Response
    try {
      response = await fetch(`${apiUrl}${path}`, {
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

  // ── fetchFormData ────────────────────────────────────────────────────────

  async function fetchFormData<T>(
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
      response = await fetch(`${apiUrl}${path}`, {
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

  return { ...api, fetchBlob, fetchFormData, refreshAccessToken, switchMembershipToken, buildHeaders }
}

export type ApiClient = ReturnType<typeof createApiClient>
