/**
 * Tests unitaires pour errors/normalizer.ts
 *
 * Couvre : normalizeError avec AxiosError (401, 403, 404, 422, 429, 500),
 * NetworkError (ECONNABORTED, ERR_NETWORK), ChunkLoadError,
 * Error generique, input non-Error, passthrough AppError.
 */
import { describe, it, expect } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import { normalizeError } from '../normalizer'
import {
  AppError,
  NetworkError,
  AuthError,
  ValidationError,
  NotFoundError,
  ForbiddenError,
  ServerError,
  ChunkLoadError,
} from '../types'

// Helper to create a fake AxiosError with response
function makeAxiosError(
  status: number,
  data: unknown = {},
  code?: string,
): AxiosError {
  const headers = new AxiosHeaders()
  const error = new AxiosError(
    `Request failed with status code ${status}`,
    code || 'ERR_BAD_RESPONSE',
    undefined,
    undefined,
    {
      status,
      data,
      statusText: 'Error',
      headers,
      config: { headers } as any,
    },
  )
  return error
}

// Helper: AxiosError without response (network error)
function makeNetworkAxiosError(code: string): AxiosError {
  const error = new AxiosError('Network Error', code)
  // No response property
  return error
}

// ── Passthrough AppError ─────────────────────────────────────────────

describe('normalizeError — passthrough AppError', () => {
  it('retourne le meme AppError si deja AppError', () => {
    const appErr = new AppError({ message: 'existing', category: 'unknown' })
    expect(normalizeError(appErr)).toBe(appErr)
  })

  it('retourne le meme NetworkError si deja sous-classe AppError', () => {
    const netErr = new NetworkError('no connection')
    expect(normalizeError(netErr)).toBe(netErr)
  })
})

// ── ChunkLoadError ───────────────────────────────────────────────────

describe('normalizeError — ChunkLoadError', () => {
  it('detecte un echec d import dynamique', () => {
    const err = new TypeError('Failed to fetch dynamically imported module /chunk-abc.js')
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ChunkLoadError)
    expect(result.category).toBe('chunk_load')
  })

  it('detecte un echec de chargement de chunk', () => {
    const err = new TypeError('Loading chunk 5 failed')
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ChunkLoadError)
  })
})

// ── Erreurs reseau ───────────────────────────────────────────────────

describe('normalizeError — erreurs reseau', () => {
  it('ECONNABORTED produit NetworkError', () => {
    const err = makeNetworkAxiosError('ECONNABORTED')
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(NetworkError)
    expect(result.category).toBe('network')
    expect(result.retryable).toBe(true)
  })

  it('ERR_NETWORK produit NetworkError', () => {
    const err = makeNetworkAxiosError('ERR_NETWORK')
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(NetworkError)
  })

  it('sans reponse et code inconnu produit quand meme NetworkError', () => {
    const err = makeNetworkAxiosError('UNKNOWN_CODE')
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(NetworkError)
  })
})

// ── HTTP 401 ─────────────────────────────────────────────────────────

describe('normalizeError — 401 AuthError', () => {
  it('produit AuthError', () => {
    const err = makeAxiosError(401, { detail: 'Token expired' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(AuthError)
    expect(result.category).toBe('auth')
  })

  it('extrait le message serveur depuis detail', () => {
    const err = makeAxiosError(401, { detail: 'Session expiree' })
    const result = normalizeError(err)
    expect(result.message).toBe('Session expiree')
  })

  it('utilise le message par defaut si pas de detail', () => {
    const err = makeAxiosError(401, {})
    const result = normalizeError(err)
    expect(result.message).toContain('Session')
  })
})

// ── HTTP 403 ─────────────────────────────────────────────────────────

describe('normalizeError — 403 ForbiddenError', () => {
  it('produit ForbiddenError', () => {
    const err = makeAxiosError(403, { detail: 'Access denied' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ForbiddenError)
    expect(result.category).toBe('forbidden')
  })

  it('extrait le message', () => {
    const err = makeAxiosError(403, { message: 'CSRF invalid' })
    const result = normalizeError(err)
    expect(result.message).toBe('CSRF invalid')
  })
})

// ── HTTP 404 ─────────────────────────────────────────────────────────

describe('normalizeError — 404 NotFoundError', () => {
  it('produit NotFoundError', () => {
    const err = makeAxiosError(404, { detail: 'Not found' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(NotFoundError)
    expect(result.category).toBe('not_found')
  })
})

// ── HTTP 422 / 400 / 409 ────────────────────────────────────────────

describe('normalizeError — erreurs de validation', () => {
  it('422 produit ValidationError', () => {
    const err = makeAxiosError(422, {
      detail: [{ loc: ['body', 'email'], msg: 'Invalid email', type: 'value_error' }],
    })
    const result = normalizeError(err) as ValidationError
    expect(result).toBeInstanceOf(ValidationError)
    expect(result.category).toBe('validation')
    expect(result.fieldErrors.email).toContain('Invalid email')
  })

  it('400 produit ValidationError', () => {
    const err = makeAxiosError(400, { detail: 'Bad request' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ValidationError)
  })

  it('409 produit ValidationError', () => {
    const err = makeAxiosError(409, { detail: 'Conflict' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ValidationError)
  })

  it('extrait les erreurs par champ depuis detail array 422', () => {
    const err = makeAxiosError(422, {
      detail: [
        { loc: ['body', 'name'], msg: 'Required', type: 'value_error' },
        { loc: ['body', 'name'], msg: 'Too short', type: 'value_error' },
        { loc: ['body', 'price'], msg: 'Invalid', type: 'type_error' },
      ],
    })
    const result = normalizeError(err) as ValidationError
    expect(result.fieldErrors.name).toHaveLength(2)
    expect(result.fieldErrors.price).toHaveLength(1)
  })

  it('400 a des fieldErrors vides', () => {
    const err = makeAxiosError(400, { detail: 'Bad' })
    const result = normalizeError(err) as ValidationError
    expect(result.fieldErrors).toEqual({})
  })
})

// ── HTTP 429 ─────────────────────────────────────────────────────────

describe('normalizeError — 429 rate limit', () => {
  it('produit NetworkError', () => {
    const err = makeAxiosError(429, {})
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(NetworkError)
    expect(result.message).toContain('requetes')
  })
})

// ── HTTP 5xx ─────────────────────────────────────────────────────────

describe('normalizeError — erreurs serveur', () => {
  it('500 produit ServerError', () => {
    const err = makeAxiosError(500, { detail: 'Internal error' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ServerError)
    expect(result.category).toBe('server')
    expect(result.retryable).toBe(true)
  })

  it('502 produit ServerError', () => {
    const err = makeAxiosError(502, {})
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ServerError)
  })

  it('extrait le message serveur pour 500', () => {
    const err = makeAxiosError(500, { detail: 'DB connection lost' })
    const result = normalizeError(err)
    expect(result.message).toBe('DB connection lost')
  })
})

// ── Erreur generique ────────────────────────────────────────────────

describe('normalizeError — erreur generique', () => {
  it('encapsule une Error generique en AppError', () => {
    const err = new Error('Something went wrong')
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(AppError)
    expect(result.message).toBe('Something went wrong')
    expect(result.category).toBe('unknown')
  })
})

// ── Input non-Error ──────────────────────────────────────────────────

describe('normalizeError — input non-Error', () => {
  it('encapsule une string en AppError', () => {
    const result = normalizeError('string error')
    expect(result).toBeInstanceOf(AppError)
    expect(result.message).toBe('string error')
  })

  it('encapsule un number en AppError', () => {
    const result = normalizeError(42)
    expect(result).toBeInstanceOf(AppError)
    expect(result.message).toBe('42')
  })

  it('encapsule null en AppError', () => {
    const result = normalizeError(null)
    expect(result).toBeInstanceOf(AppError)
  })
})
