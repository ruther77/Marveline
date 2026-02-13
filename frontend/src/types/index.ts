// User types
export interface User {
  id: number
  email: string
  first_name: string | null
  last_name: string | null
  full_name?: string
  is_active: boolean
  is_verified: boolean
  is_superuser?: boolean
  mfa_enabled?: boolean
  has_mfa?: boolean
  tenant_id: number
  tenant_name?: string
  created_at: string
  updated_at?: string
  last_login_at?: string
}

export interface UserCreate {
  email: string
  password: string
  first_name: string
  last_name: string
  is_active?: boolean
  is_superuser?: boolean
}

export interface UserUpdate {
  email?: string
  first_name?: string
  last_name?: string
  is_active?: boolean
  is_superuser?: boolean
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

export interface RegisterRequest {
  email: string
  password: string
  first_name: string
  last_name: string
}

export interface MFAVerifyRequest {
  code: string
  mfa_session_token: string
}

export interface MFASetupResponse {
  secret: string
  provisioning_uri: string
  qr_code_base64?: string
}

// Session types
export interface Session {
  id: string
  user_id: number
  tenant_id: number
  ip_address: string
  user_agent: string
  is_current: boolean
  is_active: boolean
  created_at: string
  updated_at: string
  last_seen_at: string
  device_type: string
  browser: string
  os: string
}

// Audit types
export interface AuditLog {
  id: number
  user_id: number
  action: string
  resource: string
  resource_id: string
  details: Record<string, unknown>
  ip_address: string
  user_agent: string
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
