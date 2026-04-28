/**
 * Tests unitaires pour schemas/payment.ts
 */
import { describe, it, expect } from 'vitest'
import { paymentCreateSchema } from '../payment'

const base = {
  amount_euros: 50,
  payment_method: 'card' as const,
  payment_date: '2026-03-01',
  is_deposit: false,
}

describe('paymentCreateSchema', () => {
  it('valide un paiement complet', () => {
    const result = paymentCreateSchema.parse(base)
    expect(result.amount_euros).toBe(5000) // centimes
    expect(result.payment_method).toBe('card')
    expect(result.is_deposit).toBe(false)
  })

  it('is_deposit défaut à false si absent', () => {
    const { is_deposit, ...rest } = base
    const result = paymentCreateSchema.parse(rest)
    expect(result.is_deposit).toBe(false)
  })

  it('notes est optionnel', () => {
    const result = paymentCreateSchema.parse({ ...base, notes: 'Acompte client' })
    expect(result.notes).toBe('Acompte client')
  })

  it('rejette un montant négatif', () => {
    expect(() => paymentCreateSchema.parse({ ...base, amount_euros: -10 })).toThrow()
  })

  it('rejette une date invalide', () => {
    expect(() => paymentCreateSchema.parse({ ...base, payment_date: '01/03/2026' })).toThrow()
  })

  it('rejette une méthode de paiement inconnue', () => {
    expect(() => paymentCreateSchema.parse({ ...base, payment_method: 'crypto' })).toThrow()
  })
})
