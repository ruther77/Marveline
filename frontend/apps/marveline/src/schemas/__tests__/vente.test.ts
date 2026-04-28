/**
 * Tests unitaires pour schemas/vente.ts
 */
import { describe, it, expect } from 'vitest'
import { venteCreateSchema, ventePaymentSchema, venteRefundSchema } from '../vente'

describe('venteCreateSchema', () => {
  it('valide une vente complète', () => {
    const result = venteCreateSchema.parse({
      customer_id: 1,
      lines: [{ product_id: 2, quantity: 1, unit_price_euros: 150 }],
    })
    expect(result.lines[0].unit_price_euros).toBe(15000)
  })

  it('rejette lines vide', () => {
    expect(() =>
      venteCreateSchema.parse({
        customer_id: 1,
        lines: [],
      })
    ).toThrow()
  })

  it('deposit_pct optionnel — 0 à 100', () => {
    const result = venteCreateSchema.parse({
      customer_id: 1,
      lines: [{ product_id: 1, quantity: 1, unit_price_euros: 100 }],
      deposit_pct: 30,
    })
    expect(result.deposit_pct).toBe(30)
  })

  it('rejette deposit_pct > 100', () => {
    expect(() =>
      venteCreateSchema.parse({
        customer_id: 1,
        lines: [{ product_id: 1, quantity: 1, unit_price_euros: 100 }],
        deposit_pct: 110,
      })
    ).toThrow()
  })
})

describe('ventePaymentSchema', () => {
  it('convertit amount_euros en centimes', () => {
    const result = ventePaymentSchema.parse({
      amount_euros: 75,
      payment_method: 'transfer',
      payment_date: '2026-03-15',
    })
    expect(result.amount_euros).toBe(7500)
    expect(result.is_deposit).toBe(false)
  })
})

describe('venteRefundSchema', () => {
  it('valide un remboursement', () => {
    const result = venteRefundSchema.parse({
      amount_euros: 50,
      reason: 'Article non livré',
      method: 'cash',
    })
    expect(result.amount_euros).toBe(5000)
    expect(result.reason).toBe('Article non livré')
  })

  it('rejette une raison vide', () => {
    expect(() =>
      venteRefundSchema.parse({ amount_euros: 50, reason: '', method: 'cash' })
    ).toThrow()
  })
})
