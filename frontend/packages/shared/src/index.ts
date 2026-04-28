// API Client
export { createApiClient } from './api/client'
export type { ApiClient, ApiClientConfig } from './api/client'

// Stores — MassaCorp auth
export { massacorpTokenStore } from './stores/massacorpTokenStore'
export {
  useMassaCorpAuthStore,
  configureMassaCorpAuth,
  getMassaCorpApi,
} from './stores/massacorpAuthStore'
export type {
  MassaCorpTenant,
  MassaCorpUser,
  MassaCorpAuthConfig,
} from './stores/massacorpAuthStore'

// Errors
export {
  AppError,
  AuthError,
  ForbiddenError,
  NetworkError,
  NotFoundError,
  ServerError,
  ValidationError,
} from './errors/types'
export { normalizeError } from './errors/normalizer'
