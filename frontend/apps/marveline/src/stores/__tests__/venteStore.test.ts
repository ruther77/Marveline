/**
 * Tests unitaires pour stores/venteStore.ts
 * Machine d'états vente + CRUD liste
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useVenteStore, canVenteTransition, assertVenteTransition } from '../venteStore'

beforeEach(() => {
  useVenteStore.getState().reset()
})

// ─── Machine d'états ──────────────────────────────────────────────────────────

describe('venteStore - canVenteTransition', () => {
  it('draft → pending : autorisé', () => {
    expect(canVenteTransition('draft', 'pending')).toBe(true)
  })

  it('draft → cancelled : autorisé', () => {
    expect(canVenteTransition('draft', 'cancelled')).toBe(true)
  })

  it('pending → deposit_paid : autorisé', () => {
    expect(canVenteTransition('pending', 'deposit_paid')).toBe(true)
  })

  it('pending → fully_paid : autorisé', () => {
    expect(canVenteTransition('pending', 'fully_paid')).toBe(true)
  })

  it('deposit_paid → fully_paid : autorisé', () => {
    expect(canVenteTransition('deposit_paid', 'fully_paid')).toBe(true)
  })

  it('fully_paid → refunded : autorisé', () => {
    expect(canVenteTransition('fully_paid', 'refunded')).toBe(true)
  })

  it('cancelled → * : aucune transition', () => {
    expect(canVenteTransition('cancelled', 'draft')).toBe(false)
    expect(canVenteTransition('cancelled', 'pending')).toBe(false)
  })

  it('refunded → * : aucune transition', () => {
    expect(canVenteTransition('refunded', 'pending')).toBe(false)
  })

  it('état inconnu → false', () => {
    expect(canVenteTransition('unknown_state', 'pending')).toBe(false)
  })
})

describe('venteStore - assertVenteTransition', () => {
  it('ne throw pas si transition valide', () => {
    expect(() => assertVenteTransition('draft', 'pending')).not.toThrow()
  })

  it('throw si transition invalide', () => {
    expect(() => assertVenteTransition('cancelled', 'draft'))
      .toThrow('Transition invalide : cancelled → draft')
  })
})

// ─── CRUD liste ───────────────────────────────────────────────────────────────

describe('venteStore - setList / upsertListItem / removeListItem', () => {
  it('setList remplace tout', () => {
    useVenteStore.getState().setList([{ id: 1 } as any, { id: 2 } as any], 10)
    expect(useVenteStore.getState().list).toHaveLength(2)
    expect(useVenteStore.getState().total).toBe(10)
  })

  it('upsertListItem insère si absent', () => {
    useVenteStore.getState().setList([{ id: 1, status: 'draft' } as any], 1)
    useVenteStore.getState().upsertListItem({ id: 2, status: 'pending' } as any)

    expect(useVenteStore.getState().list[0].id).toBe(2) // tête
    expect(useVenteStore.getState().total).toBe(2)
  })

  it('upsertListItem met à jour en place', () => {
    useVenteStore.getState().setList([{ id: 1, status: 'draft' } as any], 1)
    useVenteStore.getState().upsertListItem({ id: 1, status: 'pending' } as any)

    expect(useVenteStore.getState().list).toHaveLength(1)
    expect(useVenteStore.getState().list[0].status).toBe('pending')
  })

  it('removeListItem supprime, décrémente, efface selectedId', () => {
    useVenteStore.getState().setList([{ id: 1 } as any, { id: 2 } as any], 2)
    useVenteStore.getState().setSelectedId(1)

    useVenteStore.getState().removeListItem(1)

    expect(useVenteStore.getState().list).toHaveLength(1)
    expect(useVenteStore.getState().total).toBe(1)
    expect(useVenteStore.getState().selectedId).toBeNull()
  })

  it('removeListItem efface detail si correspond', () => {
    useVenteStore.getState().setDetail({ id: 3 } as any)
    useVenteStore.getState().removeListItem(3)
    expect(useVenteStore.getState().detail).toBeNull()
  })
})

// ─── reset ────────────────────────────────────────────────────────────────────

describe('venteStore - reset', () => {
  it('remet tout à zéro', () => {
    useVenteStore.getState().setList([{ id: 1 } as any], 1)
    useVenteStore.getState().setSelectedId(1)

    useVenteStore.getState().reset()

    expect(useVenteStore.getState().list).toHaveLength(0)
    expect(useVenteStore.getState().total).toBe(0)
    expect(useVenteStore.getState().selectedId).toBeNull()
  })
})
