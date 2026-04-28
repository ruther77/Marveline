/**
 * Tests unitaires pour schemas/devis.ts
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { devisLineSchema, devisCreateSchema, devisStepClientSchema, devisNegotiationSchema } from '../devis'

// ─── devisLineSchema ──────────────────────────────────────────────────────────

describe('devisLineSchema', () => {
  it('convertit unit_price_euros en centimes', () => {
    const result = devisLineSchema.parse({ product_id: 1, quantity: 2, unit_price_euros: 30 })
    expect(result.unit_price_euros).toBe(3000)
    expect(result.quantity).toBe(2)
  })

  it('rejette quantité 0', () => {
    expect(() => devisLineSchema.parse({ product_id: 1, quantity: 0, unit_price_euros: 10 })).toThrow()
  })

  it('rejette product_id négatif', () => {
    expect(() => devisLineSchema.parse({ product_id: -1, quantity: 1, unit_price_euros: 10 })).toThrow()
  })
})

// ─── devisCreateSchema ────────────────────────────────────────────────────────
// Note: valid_until doit être dans le futur → on forge une date future dynamique

const tomorrow = new Date()
tomorrow.setDate(tomorrow.getDate() + 30)
const validUntil = tomorrow.toISOString().slice(0, 10)

describe('devisCreateSchema', () => {
  it('valide un devis complet', () => {
    const result = devisCreateSchema.parse({
      customer_id: 1,
      event_date: '2026-07-01',
      valid_until: validUntil,
      lines: [{ product_id: 1, quantity: 3, unit_price_euros: 50 }],
    })
    expect(result.lines[0].unit_price_euros).toBe(5000)
  })

  it('rejette lines vide', () => {
    expect(() =>
      devisCreateSchema.parse({
        customer_id: 1,
        event_date: '2026-07-01',
        valid_until: validUntil,
        lines: [],
      })
    ).toThrow()
  })

  it('rejette valid_until dans le passé', () => {
    expect(() =>
      devisCreateSchema.parse({
        customer_id: 1,
        event_date: '2026-07-01',
        valid_until: '2020-01-01',
        lines: [{ product_id: 1, quantity: 1, unit_price_euros: 10 }],
      })
    ).toThrow()
  })
})

// ─── devisNegotiationSchema ───────────────────────────────────────────────────

describe('devisNegotiationSchema', () => {
  it('valide un message seul', () => {
    const result = devisNegotiationSchema.parse({ message: 'Peut-on avoir une réduction ?' })
    expect(result.message).toBeTruthy()
  })

  it('valide un message avec montant proposé', () => {
    const result = devisNegotiationSchema.parse({
      message: 'Proposition',
      proposed_amount_euros: 500,
    })
    expect((result as any).proposed_amount_euros).toBe(50000)
  })

  it('rejette un message vide', () => {
    expect(() => devisNegotiationSchema.parse({ message: '' })).toThrow()
  })
})
