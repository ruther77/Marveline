import { AxiosError } from 'axios'
import {
  AppError,
  NetworkError,
  AuthError,
  ValidationError,
  NotFoundError,
  ForbiddenError,
  ServerError,
  ChunkLoadError,
} from './types'
import { STATUS_CATEGORY_MAP } from './constants'

/**
 * Extract a human-readable message from an Axios error response body.
 * Backend may return { detail: "..." } or { message: "..." } or { detail: [...] }.
 */
function extractServerMessage(data: unknown): string | undefined {
  if (!data || typeof data !== 'object') return undefined
  const obj = data as Record<string, unknown>

  if (typeof obj.detail === 'string') return obj.detail
  if (typeof obj.message === 'string') return obj.message

  // FastAPI validation errors: { detail: [{ msg, loc, type }] }
  if (Array.isArray(obj.detail)) {
    return obj.detail
      .map((e: Record<string, unknown>) => e.msg || String(e))
      .join('. ')
  }

  return undefined
}

/**
 * Extract field-level errors from FastAPI 422 responses.
 * Returns { field_name: ["error message"] }
 */
function extractFieldErrors(data: unknown): Record<string, string[]> {
  if (!data || typeof data !== 'object') return {}
  const obj = data as Record<string, unknown>

  if (!Array.isArray(obj.detail)) return {}

  const fields: Record<string, string[]> = {}
  for (const err of obj.detail) {
    const loc = (err as Record<string, unknown>).loc as unknown[]
    const msg = String((err as Record<string, unknown>).msg || '')
    // loc is typically ["body", "field_name"]
    const fieldName = loc?.length > 1 ? String(loc[loc.length - 1]) : 'general'
    if (!fields[fieldName]) fields[fieldName] = []
    fields[fieldName].push(msg)
  }
  return fields
}

/**
 * Normalize any error into an AppError subclass.
 */
export function normalizeError(error: unknown): AppError {
  // Already an AppError
  if (error instanceof AppError) return error

  // Chunk loading failure (dynamic import)
  if (
    error instanceof TypeError &&
    (error.message.includes('Failed to fetch dynamically imported module') ||
      error.message.includes('Loading chunk'))
  ) {
    return new ChunkLoadError(error)
  }

  // Axios error
  if (error instanceof AxiosError) {
    return normalizeAxiosError(error)
  }

  // Generic Error
  if (error instanceof Error) {
    return new AppError({
      message: error.message,
      category: 'unknown',
      retryable: false,
      original: error,
    })
  }

  // Something else entirely
  return new AppError({
    message: String(error),
    category: 'unknown',
    retryable: false,
    original: error,
  })
}

function normalizeAxiosError(error: AxiosError): AppError {
  // No response = network error
  if (!error.response) {
    if (error.code === 'ECONNABORTED' || error.code === 'ERR_NETWORK') {
      return new NetworkError(
        'Le serveur ne repond pas. Verifiez votre connexion.',
        error,
      )
    }
    return new NetworkError(
      'Impossible de joindre le serveur.',
      error,
    )
  }

  const { status, data } = error.response
  const serverMessage = extractServerMessage(data)

  // Auth errors
  if (status === 401) {
    return new AuthError(
      serverMessage || 'Session expiree.',
      status,
      undefined,
      error,
    )
  }

  if (status === 403) {
    return new ForbiddenError(
      serverMessage || 'Acces refuse.',
      error,
    )
  }

  // Not found
  if (status === 404) {
    return new NotFoundError(
      serverMessage || 'Ressource introuvable.',
      error,
    )
  }

  // Validation
  if (status === 422 || status === 400 || status === 409) {
    return new ValidationError(
      serverMessage || 'Donnees invalides.',
      status === 422 ? extractFieldErrors(data) : {},
      error,
    )
  }

  // Rate limiting
  if (status === 429) {
    return new NetworkError(
      'Trop de requetes. Patientez quelques instants.',
      error,
    )
  }

  // Server errors (5xx)
  if (status >= 500) {
    return new ServerError(
      serverMessage || 'Erreur interne du serveur.',
      status,
      error,
    )
  }

  // Fallback: use category map or unknown
  const category = STATUS_CATEGORY_MAP[status] || 'unknown'
  return new AppError({
    message: serverMessage || `Erreur HTTP ${status}`,
    category,
    status,
    retryable: status >= 500,
    original: error,
  })
}
