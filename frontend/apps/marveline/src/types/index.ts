/**
 * Claims JWT access token v3 (§01-CRYPTO-JWT §1.2 + décision D2 §06 §6.12).
 * Utilisés côté client pour display (did, sid) — jamais pour auth (non vérifiés).
 */
export interface TokenClaims {
  sub: string          // user_id (string — RFC 7519)
  tid: string          // tenant_id (string)
  did: string          // device_id
  sid: string          // session_id (D2 : présent dans AT pour anti-IDOR §06)
  role: string         // rôle RBAC (display uniquement — les scopes font foi)
  scopes: string[]     // scopes accordés (source de vérité RBAC)
  exp: number
  iat: number
  jti: string
}

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
  password_change_required?: boolean
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

export interface UserInviteRequest {
  email: string
  role?: string
  first_name?: string
  last_name?: string
}

export interface UserInviteResponse {
  id: number
  email: string
  role: string
  invite_sent: boolean
}

// Auth types
export interface LoginRequest {
  email: string
  password: string
  captcha_token?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in?: number
  password_change_required?: boolean  // INC-07 : forcé si admin ou HIBP breach
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

// IAM v2 types — Account (identité globale) + TenantMembership
export interface AccountInfo {
  account_id: number
  email: string
  first_name: string
  last_name: string
  tenant_id: number
  membership_id: number
  role_name: string
  is_active: boolean
  password_change_required: boolean
  scopes: string[]
}

export interface LoginV2Request {
  email: string
  password: string
  tenant_id: number
}

// Session types
export interface Session {
  session_id: string
  device_id?: string
  ip_address: string
  user_agent: string
  created_at: string
  last_activity: string
  is_current?: boolean
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
  skip: number
  limit: number
}

// Re-exports
export type { ReservationStatus, ReservationLine, ReservationList, ReservationDetail, ReservationCreate, ReservationUpdate, PaginatedReservations, ReservationRisk, PreCheckItem, ReservationExtension, ReservationDetailFull } from './reservation'
export type { CustomerType, CustomerList, PaginatedCustomers } from './customer'
export type { DeliveryZone, DeliveryZoneCreate, DeliveryZoneUpdate } from './delivery_zone'
export type { ProductVariant, ProductVariantCreate, ProductVariantUpdate, ProductColor } from './product_variant'
export type { DevisStatus, DevisModuleType, DevisLigne, DevisListItem, DevisDetail, DevisCreate, DevisModule, DevisPhase, DevisVersion, DevisNegotiationEntry, DevisChangeRequest, DevisDetailFull } from './devis'
export type { VenteStatus, VenteLigne, VenteListItem, VentePayment, VenteDetail, VenteDetailFull } from './vente'
export type { InvoiceStatus, InvoiceListItem, InvoiceDetail, InvoiceDetailFull, InvoiceType, CreditNote, InvoiceAuditEntry } from './invoice'
export type { EventStatus, EventIncident, IncidentAction, EventListItem, EventDetailFull } from './event'
export type { PricingRuleType, PricingTier, PricingRule, PricingRuleCreate } from './pricing'
export type { ItemCondition, DamageCategory, DamageSeverity, DepartureCheckItem, DamageDeclaration, ReturnCheckItem, DepartureInventory, ReturnInventory } from './operations'
export type { StockItemStatus, StockItem, ProductStockDetail, ProductStockBatchResponse, StockItemHistoryEntry, StockItemHistory } from './stock_item'
export type { Collection, CollectionWithProducts, CollectionCreate, CollectionUpdate, CollectionListResponse } from './collection'
