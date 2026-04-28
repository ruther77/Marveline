/**
 * Tests unitaires pour stores/cartStore.ts
 * Zustand + persist — testé via getState(), sans rendu React.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useCartStore } from '../cartStore'

const resetCart = () => useCartStore.getState().reset()

beforeEach(resetCart)

// ─── État initial ────────────────────────────────────────────────────────────

describe('cartStore - état initial', () => {
  it('panier vide par défaut', () => {
    const { lines, mode, customer_id, notes } = useCartStore.getState()
    expect(lines).toHaveLength(0)
    expect(mode).toBe('devis')
    expect(customer_id).toBeNull()
    expect(notes).toBe('')
  })

  it('getTotalCents = 0 si panier vide', () => {
    expect(useCartStore.getState().getTotalCents()).toBe(0)
  })

  it('getLineCount = 0 si panier vide', () => {
    expect(useCartStore.getState().getLineCount()).toBe(0)
  })
})

// ─── setMode ─────────────────────────────────────────────────────────────────

describe('cartStore - setMode', () => {
  it('passe en mode reservation', () => {
    useCartStore.getState().setMode('reservation')
    expect(useCartStore.getState().mode).toBe('reservation')
  })

  it('repasse en mode devis', () => {
    useCartStore.getState().setMode('reservation')
    useCartStore.getState().setMode('devis')
    expect(useCartStore.getState().mode).toBe('devis')
  })
})

// ─── addLine ──────────────────────────────────────────────────────────────────

describe('cartStore - addLine', () => {
  it('ajoute une ligne avec subtotal_cents calculé', () => {
    useCartStore.getState().addLine({
      product_id: 1,
      product_name: 'Table ronde',
      quantity: 2,
      unit_price_cents: 1500,
      available_quantity: 10,
    })

    const { lines } = useCartStore.getState()
    expect(lines).toHaveLength(1)
    expect(lines[0].subtotal_cents).toBe(3000) // 2 × 1500
    expect(lines[0].product_name).toBe('Table ronde')
    expect(lines[0].id).toBeTruthy() // UUID généré
  })

  it('addLine sur même produit additionne les quantités', () => {
    useCartStore.getState().addLine({
      product_id: 1,
      product_name: 'Table',
      quantity: 2,
      unit_price_cents: 1500,
      available_quantity: 10,
    })
    useCartStore.getState().addLine({
      product_id: 1,
      product_name: 'Table',
      quantity: 3,
      unit_price_cents: 1500,
      available_quantity: 10,
    })

    const { lines } = useCartStore.getState()
    expect(lines).toHaveLength(1) // pas de doublon
    expect(lines[0].quantity).toBe(5)
    expect(lines[0].subtotal_cents).toBe(7500) // 5 × 1500
  })

  it('ajoute deux produits différents', () => {
    useCartStore.getState().addLine({ product_id: 1, product_name: 'Table', quantity: 1, unit_price_cents: 2000, available_quantity: 5 })
    useCartStore.getState().addLine({ product_id: 2, product_name: 'Chaise', quantity: 4, unit_price_cents: 500, available_quantity: 20 })

    expect(useCartStore.getState().lines).toHaveLength(2)
  })
})

// ─── updateLine ───────────────────────────────────────────────────────────────

describe('cartStore - updateLine', () => {
  it('met à jour la quantité et recalcule le subtotal', () => {
    useCartStore.getState().addLine({ product_id: 1, product_name: 'Table', quantity: 2, unit_price_cents: 1000, available_quantity: 10 })
    const lineId = useCartStore.getState().lines[0].id

    useCartStore.getState().updateLine(lineId, { quantity: 5 })

    const line = useCartStore.getState().lines[0]
    expect(line.quantity).toBe(5)
    expect(line.subtotal_cents).toBe(5000)
  })

  it('ne touche pas les autres lignes', () => {
    useCartStore.getState().addLine({ product_id: 1, product_name: 'A', quantity: 1, unit_price_cents: 100, available_quantity: 5 })
    useCartStore.getState().addLine({ product_id: 2, product_name: 'B', quantity: 2, unit_price_cents: 200, available_quantity: 5 })
    const lineId = useCartStore.getState().lines[0].id

    useCartStore.getState().updateLine(lineId, { quantity: 10 })

    expect(useCartStore.getState().lines[1].quantity).toBe(2) // non modifié
  })
})

// ─── removeLine ───────────────────────────────────────────────────────────────

describe('cartStore - removeLine', () => {
  it('supprime la ligne par ID', () => {
    useCartStore.getState().addLine({ product_id: 1, product_name: 'Table', quantity: 1, unit_price_cents: 1000, available_quantity: 5 })
    const lineId = useCartStore.getState().lines[0].id

    useCartStore.getState().removeLine(lineId)

    expect(useCartStore.getState().lines).toHaveLength(0)
  })

  it('laisse les autres lignes intactes', () => {
    useCartStore.getState().addLine({ product_id: 1, product_name: 'A', quantity: 1, unit_price_cents: 100, available_quantity: 5 })
    useCartStore.getState().addLine({ product_id: 2, product_name: 'B', quantity: 1, unit_price_cents: 200, available_quantity: 5 })
    const lineId = useCartStore.getState().lines[0].id

    useCartStore.getState().removeLine(lineId)

    expect(useCartStore.getState().lines).toHaveLength(1)
    expect(useCartStore.getState().lines[0].product_id).toBe(2)
  })
})

// ─── clearLines ───────────────────────────────────────────────────────────────

describe('cartStore - clearLines', () => {
  it('vide toutes les lignes sans toucher customer_id', () => {
    useCartStore.getState().addLine({ product_id: 1, product_name: 'A', quantity: 1, unit_price_cents: 100, available_quantity: 5 })
    useCartStore.getState().setCustomer(42)

    useCartStore.getState().clearLines()

    expect(useCartStore.getState().lines).toHaveLength(0)
    expect(useCartStore.getState().customer_id).toBe(42) // non touché
  })
})

// ─── Totaux ───────────────────────────────────────────────────────────────────

describe('cartStore - getTotalCents / getLineCount', () => {
  it('getTotalCents somme tous les subtotaux', () => {
    useCartStore.getState().addLine({ product_id: 1, product_name: 'A', quantity: 2, unit_price_cents: 1000, available_quantity: 5 }) // 2000
    useCartStore.getState().addLine({ product_id: 2, product_name: 'B', quantity: 3, unit_price_cents: 500, available_quantity: 5 })  // 1500

    expect(useCartStore.getState().getTotalCents()).toBe(3500)
  })

  it('getLineCount retourne le nombre de lignes distinctes', () => {
    useCartStore.getState().addLine({ product_id: 1, product_name: 'A', quantity: 5, unit_price_cents: 100, available_quantity: 10 })
    useCartStore.getState().addLine({ product_id: 2, product_name: 'B', quantity: 2, unit_price_cents: 200, available_quantity: 10 })

    expect(useCartStore.getState().getLineCount()).toBe(2) // lignes, pas items
  })
})

// ─── hasProduct ───────────────────────────────────────────────────────────────

describe('cartStore - hasProduct', () => {
  it('retourne true si le produit est dans le panier', () => {
    useCartStore.getState().addLine({ product_id: 5, product_name: 'X', quantity: 1, unit_price_cents: 100, available_quantity: 5 })

    expect(useCartStore.getState().hasProduct(5)).toBe(true)
    expect(useCartStore.getState().hasProduct(99)).toBe(false)
  })
})

// ─── setEventInfo ─────────────────────────────────────────────────────────────

describe('cartStore - setEventInfo / setNotes', () => {
  it('met à jour les infos événement partiellement', () => {
    useCartStore.getState().setEventInfo({ event_date: '2026-05-01', event_location: 'Paris' })

    const state = useCartStore.getState()
    expect(state.event_date).toBe('2026-05-01')
    expect(state.event_location).toBe('Paris')
    expect(state.delivery_date).toBeNull() // non modifié
  })

  it('setNotes met à jour les notes', () => {
    useCartStore.getState().setNotes('Attention fragile')
    expect(useCartStore.getState().notes).toBe('Attention fragile')
  })
})

// ─── reset ────────────────────────────────────────────────────────────────────

describe('cartStore - reset', () => {
  it('remet tout à zéro', () => {
    useCartStore.getState().addLine({ product_id: 1, product_name: 'X', quantity: 2, unit_price_cents: 1000, available_quantity: 5 })
    useCartStore.getState().setCustomer(10)
    useCartStore.getState().setMode('reservation')
    useCartStore.getState().setNotes('test')

    useCartStore.getState().reset()

    const state = useCartStore.getState()
    expect(state.lines).toHaveLength(0)
    expect(state.customer_id).toBeNull()
    expect(state.mode).toBe('devis')
    expect(state.notes).toBe('')
  })
})
