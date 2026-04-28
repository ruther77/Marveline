/**
 * Tests unitaires pour schemas/operations.ts
 */
import { describe, it, expect } from 'vitest'
import {
  damageDeclarationSchema,
  departureCheckSchema,
  returnCheckSchema,
  casseDeclarationSchema,
} from '../operations'

// ─── damageDeclarationSchema ──────────────────────────────────────────────────

describe('damageDeclarationSchema', () => {
  it('valide une déclaration complète', () => {
    const result = damageDeclarationSchema.parse({
      product_id: 1,
      product_name: 'Table ronde',
      category: 'break',
      severity: 'major',
      description: 'Pied cassé',
    })
    expect(result.severity).toBe('major')
    expect(result.photo_urls).toEqual([])
  })

  it('rejette une description vide', () => {
    expect(() =>
      damageDeclarationSchema.parse({
        product_id: 1,
        product_name: 'Chaise',
        category: 'scratch',
        severity: 'minor',
        description: '',
      })
    ).toThrow()
  })

  it('rejette une photo_url invalide', () => {
    expect(() =>
      damageDeclarationSchema.parse({
        product_id: 1,
        product_name: 'Chaise',
        category: 'scratch',
        severity: 'minor',
        description: 'Égratignure',
        photo_urls: ['not-a-url'],
      })
    ).toThrow()
  })

  it('convertit estimated_cost_euros en centimes', () => {
    const result = damageDeclarationSchema.parse({
      product_id: 1,
      product_name: 'Table',
      category: 'break',
      severity: 'total_loss',
      description: 'Détruite',
      estimated_cost_euros: 300,
    })
    expect((result as any).estimated_cost_euros).toBe(30000)
  })
})

// ─── departureCheckSchema ─────────────────────────────────────────────────────

describe('departureCheckSchema', () => {
  it('valide un check départ', () => {
    const result = departureCheckSchema.parse({
      reservation_id: 10,
      items: [
        {
          line_id: 1,
          product_id: 2,
          quantity_loaded: 5,
          condition: 'good',
        },
      ],
    })
    expect(result.items[0].condition).toBe('good')
    expect(result.items[0].qr_scanned).toBe(false)
  })

  it('rejette items vide', () => {
    expect(() =>
      departureCheckSchema.parse({ reservation_id: 1, items: [] })
    ).toThrow()
  })

  it('rejette quantity_loaded négatif', () => {
    expect(() =>
      departureCheckSchema.parse({
        reservation_id: 1,
        items: [{ line_id: 1, product_id: 1, quantity_loaded: -1, condition: 'good' }],
      })
    ).toThrow()
  })
})

// ─── returnCheckSchema ────────────────────────────────────────────────────────

describe('returnCheckSchema', () => {
  it('valide un check retour avec dommages', () => {
    const result = returnCheckSchema.parse({
      reservation_id: 10,
      items: [
        {
          line_id: 1,
          product_id: 2,
          quantity_returned: 4,
          condition: 'damaged',
          damages: [
            {
              product_id: 2,
              product_name: 'Chaise',
              category: 'scratch',
              severity: 'minor',
              description: 'Légère rayure',
            },
          ],
        },
      ],
    })
    expect(result.items[0].damages).toHaveLength(1)
  })
})

// ─── casseDeclarationSchema ───────────────────────────────────────────────────

describe('casseDeclarationSchema', () => {
  it('valide une déclaration de casse', () => {
    const result = casseDeclarationSchema.parse({
      reservation_id: 5,
      product_id: 3,
      description: 'Table brisée',
      severity: 'total_loss',
      estimated_cost_euros: 250,
    })
    expect((result as any).estimated_cost_euros).toBe(25000)
  })

  it('rejette une sévérité inconnue', () => {
    expect(() =>
      casseDeclarationSchema.parse({
        reservation_id: 5,
        product_id: 3,
        description: 'Cassé',
        severity: 'extreme',
        estimated_cost_euros: 100,
      })
    ).toThrow()
  })
})
