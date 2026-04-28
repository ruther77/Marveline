import type { PaginatedResponse } from './index'

// ── Enums ────────────────────────────────────────────────────────────────────

export type LoyaltyTier = 'standard' | 'vip' | 'nouveau' | 'habitue' | 'privilegie'
export type LedgerType = 'earn' | 'redeem' | 'expire' | 'adjust' | 'bonus'
export type LedgerSource = 'restaurant' | 'epicerie' | 'referral' | 'promo' | 'welcome' | 'manual' | 'flash'
export type RewardTier = 'welcome' | 'tier_1' | 'tier_2' | 'tier_3'
export type RedemptionStatus = 'used' | 'revoked'
export type FlashOfferTarget = 'all' | 'vip'
export type FlashOfferStatus = 'scheduled' | 'active' | 'ended'

// ── Member ───────────────────────────────────────────────────────────────────

export interface LoyaltyMemberList {
  id: number
  phone: string
  first_name: string
  last_name: string
  current_tier: LoyaltyTier
  transaction_count: number
  referral_code: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface LoyaltyMemberResponse extends LoyaltyMemberList {
  tenant_id: number
  program_id: number
  customer_id?: number
  birth_month?: number
  email?: string
  tier_evaluated_at?: string
  grace_until?: string
  wallet_serial_number?: string
  wallet_platform?: string
}

export interface LoyaltyMemberCreate {
  phone: string
  first_name: string
  last_name: string
  birth_month?: number
  referral_code_used?: string
  program_id: number
}

export interface LoyaltyMemberProfile {
  member_id: number
  first_name: string
  last_name: string
  current_tier: LoyaltyTier
  points_balance: number
  cumulative_ca_cents: number
  discount_percent: number
  available_rewards: RewardAvailable[]
  has_welcome_reward: boolean
}

export type PaginatedLoyaltyMembers = PaginatedResponse<LoyaltyMemberList>

// ── Rewards ──────────────────────────────────────────────────────────────────

export interface RewardAvailable {
  reward_id: number
  name: string
  tier: RewardTier
  points_cost: number
}

export interface RewardsCatalogResponse {
  id: number
  program_id: number
  tier: RewardTier
  product_id?: number
  name: string
  description?: string
  points_cost: number
  max_cost_cents: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface RewardsCatalogCreate {
  tier: RewardTier
  product_id?: number
  name: string
  description?: string
  points_cost: number
  max_cost_cents: number
}

export interface RewardsCatalogUpdate {
  name?: string
  description?: string
  points_cost?: number
  max_cost_cents?: number
  is_active?: boolean
}

export interface RewardRedemptionResponse {
  id: number
  member_id: number
  reward_id: number
  order_id?: number
  points_spent: number
  status: RedemptionStatus
  redeemed_at: string
  revoked_at?: string
  created_at: string
  updated_at: string
}

// ── Scan / Credit ────────────────────────────────────────────────────────────

export interface ScanRequest {
  barcode: string
}

export interface CreditRequest {
  member_id: number
  amount_cents: number
  source: 'restaurant' | 'epicerie'
  order_id: number
}

export interface CreditResponse {
  points_added: number
  new_balance: number
  tier: LoyaltyTier
  flash_multiplier?: number
}

export interface RevenueCreditRequest {
  member_id: number
  amount_cents: number
  reservation_id?: number
}

// ── Flash Offers ─────────────────────────────────────────────────────────────

export interface FlashOfferCreate {
  name: string
  multiplier: number
  target: FlashOfferTarget
  starts_at: string
  ends_at: string
  program_id: number
}

export interface FlashOfferResponse {
  id: number
  program_id: number
  name: string
  multiplier: number
  target: FlashOfferTarget
  starts_at: string
  ends_at: string
  status: FlashOfferStatus
  push_sent_at?: string
  created_at: string
  updated_at: string
}

// ── Adjust ───────────────────────────────────────────────────────────────────

export interface AdjustPointsRequest {
  member_id: number
  amount: number
  reason: string
}

// ── Dashboard ────────────────────────────────────────────────────────────────

export interface LoyaltyDashboardMetrics {
  total_members: number
  active_members: number
  vip_members: number
  total_points_in_circulation: number
  points_earned_this_month: number
  points_redeemed_this_month: number
  redemption_rate: number
  churn_risk_count: number
  top_referrers: TopReferrer[]
}

export interface TopReferrer {
  member_id: number
  display_name: string
  referral_count: number
}

// ── Join ─────────────────────────────────────────────────────────────────────

export interface JoinResponse {
  member_id: number
  referral_code: string
  wallet_url?: string
  welcome_reward_available: boolean
}

// ── Redeem ───────────────────────────────────────────────────────────────────

export interface RedeemRequest {
  member_id: number
  reward_id: number
  order_id?: number
}
