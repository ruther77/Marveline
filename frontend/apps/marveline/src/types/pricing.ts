export type PricingRuleType = 'flat' | 'per_day' | 'tiered' | 'volume' | 'seasonal' | 'custom'

export interface PricingTier {
  min_qty: number
  max_qty?: number
  unit_price_cents: number
}

export interface PricingRule {
  id: number
  tenant_id: number
  name: string
  rule_type: PricingRuleType
  applies_to: 'product' | 'category' | 'all'
  target_id?: number
  discount_pct?: number
  tiers?: PricingTier[]
  valid_from?: string
  valid_to?: string
  active: boolean
}

export interface PricingRuleCreate {
  name: string
  rule_type: PricingRuleType
  applies_to: 'product' | 'category' | 'all'
  target_id?: number
  discount_pct?: number
  tiers?: PricingTier[]
  valid_from?: string
  valid_to?: string
}
