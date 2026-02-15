// --- Error categories ---

export type ErrorCategory =
  | 'network'
  | 'auth'
  | 'validation'
  | 'not_found'
  | 'forbidden'
  | 'server'
  | 'chunk_load'
  | 'unknown'

// --- Base application error ---

export class AppError extends Error {
  readonly category: ErrorCategory
  readonly status?: number
  readonly code?: string
  readonly details?: Record<string, unknown>
  readonly retryable: boolean
  readonly original?: unknown

  constructor(opts: {
    message: string
    category: ErrorCategory
    status?: number
    code?: string
    details?: Record<string, unknown>
    retryable?: boolean
    original?: unknown
  }) {
    super(opts.message)
    this.name = 'AppError'
    this.category = opts.category
    this.status = opts.status
    this.code = opts.code
    this.details = opts.details
    this.retryable = opts.retryable ?? false
    this.original = opts.original
  }
}

// --- Specialized errors ---

export class NetworkError extends AppError {
  constructor(message: string, original?: unknown) {
    super({
      message,
      category: 'network',
      retryable: true,
      original,
    })
    this.name = 'NetworkError'
  }
}

export class AuthError extends AppError {
  constructor(message: string, status: number, code?: string, original?: unknown) {
    super({
      message,
      category: 'auth',
      status,
      code,
      retryable: false,
      original,
    })
    this.name = 'AuthError'
  }
}

export class ValidationError extends AppError {
  readonly fieldErrors: Record<string, string[]>

  constructor(
    message: string,
    fieldErrors: Record<string, string[]> = {},
    original?: unknown,
  ) {
    super({
      message,
      category: 'validation',
      status: 422,
      retryable: false,
      original,
    })
    this.name = 'ValidationError'
    this.fieldErrors = fieldErrors
  }
}

export class NotFoundError extends AppError {
  constructor(message: string, original?: unknown) {
    super({
      message,
      category: 'not_found',
      status: 404,
      retryable: false,
      original,
    })
    this.name = 'NotFoundError'
  }
}

export class ForbiddenError extends AppError {
  constructor(message: string, original?: unknown) {
    super({
      message,
      category: 'forbidden',
      status: 403,
      retryable: false,
      original,
    })
    this.name = 'ForbiddenError'
  }
}

export class ServerError extends AppError {
  constructor(message: string, status: number, original?: unknown) {
    super({
      message,
      category: 'server',
      status,
      retryable: true,
      original,
    })
    this.name = 'ServerError'
  }
}

export class ChunkLoadError extends AppError {
  constructor(original?: unknown) {
    super({
      message: 'Failed to load application module',
      category: 'chunk_load',
      retryable: true,
      original,
    })
    this.name = 'ChunkLoadError'
  }
}
