/**
 * Tests unitaires pour schemas/pricing.ts
 * pricingTierSchema, pricingRuleSchema (refinements dates + tiered)
 */
import { describe, it, expect } from 'vitest'
import { pricingTierSchema, pricingRuleSchema } from '../pricing'

// ─── pricingTierSchema ────────────────────────────────────────────────────────

describe('pricingTierSchema', () => {
  it('valide un palier basique', () => {
    const result = pricingTierSchema.parse({ min_qty: 1, unit_price_cents: 2000 })
    expect(result.min_qty).toBe(1)
  })

  it('rejette min_qty = 0', () => {
    expect(() => pricingTierSchema.parse({ min_qty: 0, unit_price_cents: 2000 })).toThrow()
  })

  it('rejette unit_price_cents négatif', () => {
    expect(() => pricingTierSchema.parse({ min_qty: 1, unit_price_cents: -10 })).toThrow()
  })
})

// ─── pricingRuleSchema ────────────────────────────────────────────────────────

const baseRule = {
  name: 'Tarif week-end',
  rule_type: 'flat' as const,
  applies_to: 'product' as const,
}

describe('pricingRuleSchema - cas valides', () => {
  it('valide une règle flat simple', () => {
    const result = pricingRuleSchema.parse(baseRule)
    expect(result.name).toBe('Tarif week-end')
  })

  it('accepte des dates valides (valid_from < valid_to)', () => {
    expect(() =>
      pricingRuleSchema.parse({
        ...baseRule,
        valid_from: '2026-01-01',
        valid_to: '2026-12-31',
      })
    ).not.toThrow()
  })

  it('règle tiered avec paliers valide', () => {
    const result = pricingRuleSchema.parse({
      ...baseRule,
      rule_type: 'tiered',
      tiers: [{ min_qty: 1, unit_price_cents: 1500 }],
    })
    expect(result.rule_type).toBe('tiered')
  })
})

describe('pricingRuleSchema - refinements', () => {
  it('rejette valid_to < valid_from', () => {
    expect(() =>
      pricingRuleSchema.parse({
        ...baseRule,
        valid_from: '2026-06-01',
        valid_to: '2026-01-01',
      })
    ).toThrow()
  })

  it('rule_type=tiered sans tiers → erreur', () => {
    expect(() =>
      pricingRuleSchema.parse({ ...baseRule, rule_type: 'tiered' })
    ).toThrow()
  })

  it('rule_type=tiered avec tiers vide → erreur', () => {
    expect(() =>
      pricingRuleSchema.parse({ ...baseRule, rule_type: 'tiered', tiers: [] })
    ).toThrow()
  })

  it('rejette un nom vide', () => {
    expect(() => pricingRuleSchema.parse({ ...baseRule, name: '' })).toThrow()
  })

  it('rejette un rule_type inconnu', () => {
    expect(() => pricingRuleSchema.parse({ ...baseRule, rule_type: 'mystery' })).toThrow()
  })

  it('rejette discount_pct > 100', () => {
    expect(() =>
      pricingRuleSchema.parse({ ...baseRule, discount_pct: 150 })
    ).toThrow()
  })
})
