/**
 * Client API Loyalty pour le restaurant.
 * Endpoints staff : scan, credit, redeem.
 */
import { massacorpApi as api } from '@/api'

/** ID du programme fidélité "L'Incontournable" (restaurant + épicerie). */
export const RESTAURANT_LOYALTY_PROGRAM_ID = 1

export interface LoyaltyMemberProfile {
  member_id: number
  first_name: string
  last_name: string
  phone: string
  current_tier: string
  points_balance: number
  discount_percent: number
  has_welcome_reward: boolean
  available_rewards: RewardAvailable[]
  transaction_count: number
}

export interface RewardAvailable {
  reward_id: number
  name: string
  points_cost: number
  tier: string
}

export interface CreditResponse {
  points_earned: number
  new_balance: number
  multiplier: number
  flash_offer_active: boolean
}

export const loyaltyApi = {
  scan(barcode: string): Promise<LoyaltyMemberProfile> {
    return api.post('/loyalty/scan', { barcode })
  },

  credit(data: {
    member_id: number
    order_id: number
    amount_cts: number
    source: 'restaurant' | 'epicerie'
    program_id: number
  }): Promise<CreditResponse> {
    return api.post('/loyalty/credit', data)
  },

  redeem(data: {
    member_id: number
    reward_id: number
    order_id?: number
  }): Promise<{ success: boolean }> {
    return api.post('/loyalty/redeem', data)
  },
}
