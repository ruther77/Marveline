/**
 * Tests unitaires pour schemas/common.ts
 * amountEurosSchema, dateIsoSchema, idSchema, paymentMethodSchema
 */
import { describe, it, expect } from 'vitest'
import { amountEurosSchema, dateIsoSchema, idSchema, paymentMethodSchema } from '../common'

// ─── amountEurosSchema ────────────────────────────────────────────────────────

describe('amountEurosSchema', () => {
  it('convertit 2.50 en 250 centimes', () => {
    expect(amountEurosSchema.parse(2.5)).toBe(250)
  })

  it('convertit 0 en 0', () => {
    expect(amountEurosSchema.parse(0)).toBe(0)
  })

  it('arrondit correctement (0.015 → 2 centimes)', () => {
    expect(amountEurosSchema.parse(0.015)).toBe(2)
  })

  it('convertit 100 en 10000', () => {
    expect(amountEurosSchema.parse(100)).toBe(10000)
  })

  it('rejette un montant négatif', () => {
    expect(() => amountEurosSchema.parse(-1)).toThrow()
  })

  it('rejette une string', () => {
    expect(() => amountEurosSchema.parse('10')).toThrow()
  })
})

// ─── dateIsoSchema ────────────────────────────────────────────────────────────

describe('dateIsoSchema', () => {
  it('accepte un format YYYY-MM-DD valide', () => {
    expect(dateIsoSchema.parse('2026-01-15')).toBe('2026-01-15')
  })

  it('rejette un format DD/MM/YYYY', () => {
    expect(() => dateIsoSchema.parse('15/01/2026')).toThrow()
  })

  it('rejette une string vide', () => {
    expect(() => dateIsoSchema.parse('')).toThrow()
  })

  it('rejette YYYY-MM (sans jour)', () => {
    expect(() => dateIsoSchema.parse('2026-01')).toThrow()
  })

  it('rejette un texte libre', () => {
    expect(() => dateIsoSchema.parse('aujourd\u0027hui')).toThrow()
  })
})

// ─── idSchema ─────────────────────────────────────────────────────────────────

describe('idSchema', () => {
  it('accepte un entier positif', () => {
    expect(idSchema.parse(1)).toBe(1)
    expect(idSchema.parse(9999)).toBe(9999)
  })

  it('rejette 0', () => {
    expect(() => idSchema.parse(0)).toThrow()
  })

  it('rejette un négatif', () => {
    expect(() => idSchema.parse(-5)).toThrow()
  })

  it('rejette un flottant', () => {
    expect(() => idSchema.parse(1.5)).toThrow()
  })
})

// ─── paymentMethodSchema ──────────────────────────────────────────────────────

describe('paymentMethodSchema', () => {
  it.each(['cash', 'card', 'transfer', 'check'])('accepte "%s"', (method) => {
    expect(paymentMethodSchema.parse(method)).toBe(method)
  })

  it('rejette une valeur inconnue', () => {
    expect(() => paymentMethodSchema.parse('bitcoin')).toThrow()
  })

  it('rejette une string vide', () => {
    expect(() => paymentMethodSchema.parse('')).toThrow()
  })
})
