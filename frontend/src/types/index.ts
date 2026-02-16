// User types — aligned with backend UserInfo (GET /auth/me)
export interface User {
  id: number
  email: string
  full_name: string
  role: string
  tenant_id: number
  is_active: boolean
  permissions: string[]
  created_at: string | null
  // Extended fields from GET /users/me (UserProfileResponse)
  first_name?: string
  last_name?: string
  updated_at?: string
}

export interface UserCreate {
  email: string
  password: string
  first_name: string
  last_name: string
  role?: string
  is_active?: boolean
}

export interface UserUpdate {
  email?: string
  first_name?: string
  last_name?: string
  role?: string
  is_active?: boolean
}

// Auth types
export interface LoginRequest {
  email: string
  password: string
  captcha_token?: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user?: User
  mfa_required?: boolean
  mfa_session_token?: string
}

export interface MFAVerifyRequest {
  code: string
  mfa_session_token: string
}

export interface MFASetupResponse {
  secret: string
  provisioning_uri: string
  recovery_codes: string[]
}

// Session types
export interface Session {
  session_id: string
  ip_address: string
  user_agent: string
  created_at: string
  last_activity: string
}

// Audit types — aligned with backend AuditLogResponse
export interface AuditLog {
  id: number
  user_id: number | null
  tenant_id: number
  action: string
  entity_type: string | null
  entity_id: number | null
  changes: Record<string, unknown> | null
  description: string | null
  ip_address: string | null
  user_agent: string | null
  request_id: string | null
  created_at: string
}

// API Response types
export interface ApiError {
  error: string
  message: string
  details?: Record<string, unknown>
  request_id?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

// Re-exports
export type { ReservationStatus, ReservationLine, ReservationList, ReservationDetail, ReservationCreate, ReservationUpdate, PaginatedReservations } from './reservation'
export type { CustomerType, CustomerList, PaginatedCustomers } from './customer'
