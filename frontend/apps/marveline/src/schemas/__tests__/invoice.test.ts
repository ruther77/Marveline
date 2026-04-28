/**
 * Tests unitaires pour schemas/invoice.ts
 * invoiceCreateSchema, addPaymentSchema, chargeCreateSchema (discriminatedUnion)
 */
import { describe, it, expect } from 'vitest'
import { invoiceCreateSchema, addPaymentSchema, chargeCreateSchema } from '../invoice'

// ─── invoiceCreateSchema ──────────────────────────────────────────────────────

describe('invoiceCreateSchema', () => {
  it('valide avec issue_date < due_date', () => {
    const result = invoiceCreateSchema.parse({
      reservation_id: 1,
      issue_date: '2026-01-01',
      due_date: '2026-01-31',
    })
    expect(result.reservation_id).toBe(1)
  })

  it('valide avec issue_date === due_date', () => {
    expect(() =>
      invoiceCreateSchema.parse({
        reservation_id: 1,
        issue_date: '2026-01-15',
        due_date: '2026-01-15',
      })
    ).not.toThrow()
  })

  it('rejette due_date < issue_date', () => {
    expect(() =>
      invoiceCreateSchema.parse({
        reservation_id: 1,
        issue_date: '2026-02-01',
        due_date: '2026-01-01',
      })
    ).toThrow()
  })

  it('rejette reservation_id = 0', () => {
    expect(() =>
      invoiceCreateSchema.parse({
        reservation_id: 0,
        issue_date: '2026-01-01',
        due_date: '2026-01-31',
      })
    ).toThrow()
  })
})

// ─── addPaymentSchema ──────────────────────────────────────────────────────────

describe('addPaymentSchema', () => {
  it('transforme amount_euros en centimes', () => {
    const result = addPaymentSchema.parse({
      amount_euros: 75.5,
      payment_method: 'cash',
      payment_date: '2026-01-20',
    })
    expect(result.amount_euros).toBe(7550)
  })
})

// ─── chargeCreateSchema (discriminatedUnion) ──────────────────────────────────

describe('chargeCreateSchema - DAMAGE', () => {
  it('valide un dommage avec montant', () => {
    const result = chargeCreateSchema.parse({
      charge_type: 'DAMAGE',
      amount_euros: 200,
      description: 'Table cassée',
    })
    expect(result.charge_type).toBe('DAMAGE')
    expect((result as any).amount_euros).toBe(20000)
  })

  it('description vide → erreur', () => {
    expect(() =>
      chargeCreateSchema.parse({
        charge_type: 'DAMAGE',
        amount_euros: 100,
        description: '',
      })
    ).toThrow()
  })
})

describe('chargeCreateSchema - LABOR', () => {
  it('valide une main d\'œuvre week-end', () => {
    const result = chargeCreateSchema.parse({
      charge_type: 'LABOR',
      hours: 4,
      day_type: 'weekend',
      description: 'Montage tables',
    })
    expect(result.charge_type).toBe('LABOR')
    expect((result as any).hours).toBe(4)
  })

  it('rejette hours négatives', () => {
    expect(() =>
      chargeCreateSchema.parse({
        charge_type: 'LABOR',
        hours: -2,
        day_type: 'weekday',
        description: 'Livraison',
      })
    ).toThrow()
  })

  it('rejette un day_type inconnu', () => {
    expect(() =>
      chargeCreateSchema.parse({
        charge_type: 'LABOR',
        hours: 2,
        day_type: 'holiday',
        description: 'Travaux',
      })
    ).toThrow()
  })
})
