/**
 * Tests unitaires pour schemas/reservation.ts
 */
import { describe, it, expect } from 'vitest'
import {
  reservationCreateSchema,
  reservationUpdateSchema,
  cautionSchema,
  extendSchema,
} from '../reservation'

const baseReservation = {
  customer_id: 1,
  event_date: '2026-06-15',
  delivery_date: '2026-06-14',
  return_date: '2026-06-16',
  lines: [{ product_id: 1, quantity: 2 }],
}

// ─── reservationCreateSchema ───────────────────────────────────────────────────

describe('reservationCreateSchema', () => {
  it('valide une réservation correcte', () => {
    const result = reservationCreateSchema.parse(baseReservation)
    expect(result.customer_id).toBe(1)
    expect(result.lines).toHaveLength(1)
  })

  it('rejette delivery_date > event_date', () => {
    expect(() =>
      reservationCreateSchema.parse({
        ...baseReservation,
        delivery_date: '2026-06-20', // après event_date
      })
    ).toThrow()
  })

  it('rejette return_date < event_date', () => {
    expect(() =>
      reservationCreateSchema.parse({
        ...baseReservation,
        return_date: '2026-06-10', // avant event_date
      })
    ).toThrow()
  })

  it('rejette lines vide', () => {
    expect(() =>
      reservationCreateSchema.parse({ ...baseReservation, lines: [] })
    ).toThrow()
  })

  it('accepte delivery_date === event_date', () => {
    expect(() =>
      reservationCreateSchema.parse({
        ...baseReservation,
        delivery_date: '2026-06-15',
      })
    ).not.toThrow()
  })

  it('accepte des champs optionnels (event_type, event_name)', () => {
    const result = reservationCreateSchema.parse({
      ...baseReservation,
      event_type: 'mariage',
      event_name: 'Mariage Dupont',
      guest_count: 150,
    })
    expect(result.event_type).toBe('mariage')
  })

  it('rejette un event_type inconnu', () => {
    expect(() =>
      reservationCreateSchema.parse({
        ...baseReservation,
        event_type: 'concert',
      })
    ).toThrow()
  })
})

// ─── cautionSchema ────────────────────────────────────────────────────────────

describe('cautionSchema', () => {
  it('convertit le montant en centimes', () => {
    const result = cautionSchema.parse({ amount_euros: 500, method: 'check' })
    expect(result.amount_euros).toBe(50000)
    expect(result.method).toBe('check')
  })

  it('rejette une méthode inconnue', () => {
    expect(() => cautionSchema.parse({ amount_euros: 100, method: 'paypal' })).toThrow()
  })
})

// ─── extendSchema ─────────────────────────────────────────────────────────────

describe('extendSchema', () => {
  it('valide un prolongement avec raison', () => {
    const result = extendSchema.parse({
      new_return_date: '2026-06-20',
      reason: 'Client demande prolongation',
    })
    expect(result.reason).toBe('Client demande prolongation')
  })

  it('rejette une raison vide', () => {
    expect(() =>
      extendSchema.parse({ new_return_date: '2026-06-20', reason: '' })
    ).toThrow()
  })
})

// ─── reservationUpdateSchema ──────────────────────────────────────────────────

describe('reservationUpdateSchema', () => {
  it('accepte un objet vide (tout optionnel)', () => {
    expect(() => reservationUpdateSchema.parse({})).not.toThrow()
  })

  it('accepte la mise à jour de l\'event_date seule', () => {
    const result = reservationUpdateSchema.parse({ event_date: '2026-07-01' })
    expect(result.event_date).toBe('2026-07-01')
  })
})
