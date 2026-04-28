/**
 * Tests unitaires pour errors/types.ts
 *
 * Couvre : AppError, NetworkError, AuthError, ValidationError,
 * NotFoundError, ForbiddenError, ServerError, ChunkLoadError.
 */
import { describe, it, expect } from 'vitest'
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

// ── AppError ─────────────────────────────────────────────────────────

describe('AppError', () => {
  it('cree avec les champs requis', () => {
    const err = new AppError({
      message: 'Test error',
      category: 'unknown',
    })
    expect(err.message).toBe('Test error')
    expect(err.category).toBe('unknown')
    expect(err.retryable).toBe(false)
    expect(err.name).toBe('AppError')
  })

  it('stocke les champs optionnels', () => {
    const original = new Error('original')
    const err = new AppError({
      message: 'Full error',
      category: 'server',
      status: 500,
      code: 'INTERNAL',
      details: { key: 'value' },
      retryable: true,
      original,
    })
    expect(err.status).toBe(500)
    expect(err.code).toBe('INTERNAL')
    expect(err.details).toEqual({ key: 'value' })
    expect(err.retryable).toBe(true)
    expect(err.original).toBe(original)
  })

  it('est une instance de Error', () => {
    const err = new AppError({ message: 'test', category: 'unknown' })
    expect(err).toBeInstanceOf(Error)
  })

  it('retryable vaut false par defaut', () => {
    const err = new AppError({ message: 'test', category: 'auth' })
    expect(err.retryable).toBe(false)
  })
})

// ── NetworkError ─────────────────────────────────────────────────────

describe('NetworkError', () => {
  it('a la categorie network', () => {
    const err = new NetworkError('No connection')
    expect(err.category).toBe('network')
  })

  it('est retryable', () => {
    const err = new NetworkError('Timeout')
    expect(err.retryable).toBe(true)
  })

  it('a le nom NetworkError', () => {
    const err = new NetworkError('msg')
    expect(err.name).toBe('NetworkError')
  })

  it('est une instance de AppError', () => {
    const err = new NetworkError('msg')
    expect(err).toBeInstanceOf(AppError)
  })

  it('stocke l erreur originale', () => {
    const original = new Error('orig')
    const err = new NetworkError('msg', original)
    expect(err.original).toBe(original)
  })
})

// ── AuthError ────────────────────────────────────────────────────────

describe('AuthError', () => {
  it('a la categorie auth', () => {
    const err = new AuthError('Unauthorized', 401)
    expect(err.category).toBe('auth')
  })

  it('stocke le status', () => {
    const err = new AuthError('msg', 401)
    expect(err.status).toBe(401)
  })

  it('n est pas retryable', () => {
    const err = new AuthError('msg', 401)
    expect(err.retryable).toBe(false)
  })

  it('a le nom AuthError', () => {
    const err = new AuthError('msg', 401)
    expect(err.name).toBe('AuthError')
  })

  it('stocke le code', () => {
    const err = new AuthError('msg', 401, 'TOKEN_EXPIRED')
    expect(err.code).toBe('TOKEN_EXPIRED')
  })
})

// ── ValidationError ──────────────────────────────────────────────────

describe('ValidationError', () => {
  it('a la categorie validation', () => {
    const err = new ValidationError('Invalid')
    expect(err.category).toBe('validation')
  })

  it('a le status 422', () => {
    const err = new ValidationError('Invalid')
    expect(err.status).toBe(422)
  })

  it('stocke les erreurs par champ', () => {
    const fields = { email: ['Invalid email'] }
    const err = new ValidationError('Invalid', fields)
    expect(err.fieldErrors).toEqual(fields)
  })

  it('fieldErrors vide par defaut', () => {
    const err = new ValidationError('Invalid')
    expect(err.fieldErrors).toEqual({})
  })

  it('n est pas retryable', () => {
    const err = new ValidationError('Invalid')
    expect(err.retryable).toBe(false)
  })

  it('a le nom ValidationError', () => {
    const err = new ValidationError('msg')
    expect(err.name).toBe('ValidationError')
  })
})

// ── NotFoundError ────────────────────────────────────────────────────

describe('NotFoundError', () => {
  it('a la categorie not_found', () => {
    const err = new NotFoundError('Not found')
    expect(err.category).toBe('not_found')
  })

  it('a le status 404', () => {
    const err = new NotFoundError('msg')
    expect(err.status).toBe(404)
  })

  it('n est pas retryable', () => {
    const err = new NotFoundError('msg')
    expect(err.retryable).toBe(false)
  })
})

// ── ForbiddenError ───────────────────────────────────────────────────

describe('ForbiddenError', () => {
  it('a la categorie forbidden', () => {
    const err = new ForbiddenError('Forbidden')
    expect(err.category).toBe('forbidden')
  })

  it('a le status 403', () => {
    const err = new ForbiddenError('msg')
    expect(err.status).toBe(403)
  })

  it('n est pas retryable', () => {
    const err = new ForbiddenError('msg')
    expect(err.retryable).toBe(false)
  })
})

// ── ServerError ──────────────────────────────────────────────────────

describe('ServerError', () => {
  it('a la categorie server', () => {
    const err = new ServerError('Internal', 500)
    expect(err.category).toBe('server')
  })

  it('stocke le status', () => {
    const err = new ServerError('msg', 502)
    expect(err.status).toBe(502)
  })

  it('est retryable', () => {
    const err = new ServerError('msg', 500)
    expect(err.retryable).toBe(true)
  })

  it('a le nom ServerError', () => {
    const err = new ServerError('msg', 500)
    expect(err.name).toBe('ServerError')
  })
})

// ── ChunkLoadError ───────────────────────────────────────────────────

describe('ChunkLoadError', () => {
  it('a la categorie chunk_load', () => {
    const err = new ChunkLoadError()
    expect(err.category).toBe('chunk_load')
  })

  it('est retryable', () => {
    const err = new ChunkLoadError()
    expect(err.retryable).toBe(true)
  })

  it('a un message fixe', () => {
    const err = new ChunkLoadError()
    expect(err.message).toBe('Failed to load application module')
  })

  it('a le nom ChunkLoadError', () => {
    const err = new ChunkLoadError()
    expect(err.name).toBe('ChunkLoadError')
  })

  it('stocke l erreur originale', () => {
    const orig = new TypeError('chunk fail')
    const err = new ChunkLoadError(orig)
    expect(err.original).toBe(orig)
  })
})
