/**
 * Tests unitaires pour errors/normalizer.ts
 *
 * Couvre : normalizeError avec erreurs fetchClient (401, 403, 404, 422, 429, 500),
 * NetworkError (erreurs réseau natives), ChunkLoadError,
 * Error generique, input non-Error, passthrough AppError.
 */
import { describe, it, expect } from 'vitest'
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

// Helper: simule une erreur HTTP throwée par fetchClient (Error + status + data)
function makeFetchError(
  status: number,
  data: unknown = {},
): Error & { status: number; data?: unknown } {
  const err = new Error(`HTTP Error ${status}`) as Error & { status: number; data?: unknown }
  err.status = status
  err.data = data
  return err
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

  it('retourne le meme AuthError si deja sous-classe AppError', () => {
    const authErr = new AuthError('Session expirée', 401)
    expect(normalizeError(authErr)).toBe(authErr)
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

// ── Erreurs réseau (TypeError sans status) ───────────────────────────

describe('normalizeError — erreurs reseau generiques', () => {
  it('TypeError sans status produit AppError category unknown', () => {
    const err = new TypeError('Network Error')
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(AppError)
    expect(result.category).toBe('unknown')
    expect(result.message).toBe('Network Error')
  })

  it('NetworkError deja construite est un passthrough', () => {
    const err = new NetworkError('Impossible de joindre le serveur.')
    const result = normalizeError(err)
    expect(result).toBe(err)
    expect(result.category).toBe('network')
    expect(result.retryable).toBe(true)
  })
})

// ── HTTP 401 ─────────────────────────────────────────────────────────

describe('normalizeError — 401 AuthError', () => {
  it('produit AuthError', () => {
    const err = makeFetchError(401, { detail: 'Token expired' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(AuthError)
    expect(result.category).toBe('auth')
  })

  it('extrait le message serveur depuis detail', () => {
    const err = makeFetchError(401, { detail: 'Session expiree' })
    const result = normalizeError(err)
    expect(result.message).toBe('Session expiree')
  })

  it('utilise le message par defaut si pas de detail', () => {
    const err = makeFetchError(401, {})
    const result = normalizeError(err)
    expect(result.message).toContain('Session')
  })
})

// ── HTTP 403 ─────────────────────────────────────────────────────────

describe('normalizeError — 403 ForbiddenError', () => {
  it('produit ForbiddenError', () => {
    const err = makeFetchError(403, { detail: 'Access denied' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ForbiddenError)
    expect(result.category).toBe('forbidden')
  })

  it('extrait le message depuis message field', () => {
    const err = makeFetchError(403, { message: 'CSRF invalid' })
    const result = normalizeError(err)
    expect(result.message).toBe('CSRF invalid')
  })
})

// ── HTTP 404 ─────────────────────────────────────────────────────────

describe('normalizeError — 404 NotFoundError', () => {
  it('produit NotFoundError', () => {
    const err = makeFetchError(404, { detail: 'Not found' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(NotFoundError)
    expect(result.category).toBe('not_found')
  })
})

// ── HTTP 422 / 400 / 409 ────────────────────────────────────────────

describe('normalizeError — erreurs de validation', () => {
  it('422 produit ValidationError', () => {
    const err = makeFetchError(422, {
      detail: [{ loc: ['body', 'email'], msg: 'Invalid email', type: 'value_error' }],
    })
    const result = normalizeError(err) as ValidationError
    expect(result).toBeInstanceOf(ValidationError)
    expect(result.category).toBe('validation')
    expect(result.fieldErrors.email).toContain('Invalid email')
  })

  it('400 produit ValidationError', () => {
    const err = makeFetchError(400, { detail: 'Bad request' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ValidationError)
  })

  it('409 produit ValidationError', () => {
    const err = makeFetchError(409, { detail: 'Conflict' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ValidationError)
  })

  it('extrait les erreurs par champ depuis detail array 422', () => {
    const err = makeFetchError(422, {
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
    const err = makeFetchError(400, { detail: 'Bad' })
    const result = normalizeError(err) as ValidationError
    expect(result.fieldErrors).toEqual({})
  })
})

// ── HTTP 429 ─────────────────────────────────────────────────────────

describe('normalizeError — 429 rate limit', () => {
  it('produit NetworkError', () => {
    const err = makeFetchError(429, {})
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(NetworkError)
    expect(result.message).toContain('requetes')
  })
})

// ── HTTP 5xx ─────────────────────────────────────────────────────────

describe('normalizeError — erreurs serveur', () => {
  it('500 produit ServerError', () => {
    const err = makeFetchError(500, { detail: 'Internal error' })
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ServerError)
    expect(result.category).toBe('server')
    expect(result.retryable).toBe(true)
  })

  it('502 produit ServerError', () => {
    const err = makeFetchError(502, {})
    const result = normalizeError(err)
    expect(result).toBeInstanceOf(ServerError)
  })

  it('extrait le message serveur pour 500', () => {
    const err = makeFetchError(500, { detail: 'DB connection lost' })
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
