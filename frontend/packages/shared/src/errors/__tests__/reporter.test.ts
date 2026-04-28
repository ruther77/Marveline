/**
 * Tests unitaires pour errors/reporter.ts
 * ConsoleReporter (via getErrorReporter), setErrorReporter
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getErrorReporter, setErrorReporter, type ErrorReporter } from '../reporter'
import { AppError, NetworkError, AuthError } from '../types'

// ─── ConsoleReporter (reporter par défaut) ────────────────────────────────────

describe('getErrorReporter - reporter par défaut', () => {
  it('retourne un objet implémentant ErrorReporter', () => {
    const r = getErrorReporter()
    expect(typeof r.captureError).toBe('function')
    expect(typeof r.captureMessage).toBe('function')
    expect(typeof r.setUser).toBe('function')
  })
})

describe('ConsoleReporter.captureError', () => {
  beforeEach(() => {
    vi.spyOn(console, 'groupCollapsed').mockImplementation(() => {})
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.spyOn(console, 'groupEnd').mockImplementation(() => {})
  })
  afterEach(() => vi.restoreAllMocks())

  it('appelle console.groupCollapsed avec le message', () => {
    const error = new NetworkError('connexion perdue')
    getErrorReporter().captureError(error)
    expect(console.groupCollapsed).toHaveBeenCalled()
  })

  it('appelle console.log pour Error, Category, Status, Retryable', () => {
    const error = new AppError({ message: 'msg', category: 'server', status: 500, retryable: false })
    getErrorReporter().captureError(error)
    expect(console.log).toHaveBeenCalledTimes(4) // Error / Category / Status / Retryable
  })

  it('loggue le contexte si fourni', () => {
    const error = new AppError({ message: 'ctx error', category: 'validation', status: 422, retryable: false })
    getErrorReporter().captureError(error, { route: '/test', action: 'submit' })
    const logCalls = (console.log as ReturnType<typeof vi.fn>).mock.calls
    const contextCall = logCalls.find(([label]) => label === 'Context:')
    expect(contextCall).toBeDefined()
  })

  it('loggue l\'original si error.original est défini', () => {
    const orig = new Error('original')
    const error = new AppError({ message: 'wrapped', category: 'unknown', retryable: false, original: orig })
    getErrorReporter().captureError(error)
    const logCalls = (console.log as ReturnType<typeof vi.fn>).mock.calls
    const origCall = logCalls.find(([label]) => label === 'Original:')
    expect(origCall).toBeDefined()
  })

  it('loggue l\'utilisateur si setUser a été appelé', () => {
    const reporter = getErrorReporter()
    reporter.setUser({ id: 1, email: 'test@test.com', tenant_id: 42 })
    reporter.captureError(new AppError({ message: 'msg', category: 'unknown', retryable: false }))
    const logCalls = (console.log as ReturnType<typeof vi.fn>).mock.calls
    const userCall = logCalls.find(([label]) => label === 'User:')
    expect(userCall).toBeDefined()
  })
})

describe('ConsoleReporter.captureMessage', () => {
  afterEach(() => vi.restoreAllMocks())

  it('appelle console.warn pour level warning', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    getErrorReporter().captureMessage('attention', 'warning')
    expect(console.warn).toHaveBeenCalledWith('[REPORT] attention')
  })

  it('appelle console.info pour level info', () => {
    vi.spyOn(console, 'info').mockImplementation(() => {})
    getErrorReporter().captureMessage('information', 'info')
    expect(console.info).toHaveBeenCalledWith('[REPORT] information')
  })
})

// ─── setErrorReporter ─────────────────────────────────────────────────────────

describe('setErrorReporter', () => {
  let originalReporter: ErrorReporter

  beforeEach(() => {
    originalReporter = getErrorReporter()
  })
  afterEach(() => {
    setErrorReporter(originalReporter)
  })

  it('remplace le reporter global', () => {
    const mockReporter: ErrorReporter = {
      captureError: vi.fn(),
      captureMessage: vi.fn(),
      setUser: vi.fn(),
    }
    setErrorReporter(mockReporter)

    const error = new NetworkError('connexion perdue')
    getErrorReporter().captureError(error)

    expect(mockReporter.captureError).toHaveBeenCalledWith(error)
    expect(getErrorReporter()).toBe(mockReporter)
  })

  it('getErrorReporter retourne le nouveau reporter après setErrorReporter', () => {
    const newReporter: ErrorReporter = {
      captureError: vi.fn(),
      captureMessage: vi.fn(),
      setUser: vi.fn(),
    }
    setErrorReporter(newReporter)
    expect(getErrorReporter()).toBe(newReporter)
  })
})
