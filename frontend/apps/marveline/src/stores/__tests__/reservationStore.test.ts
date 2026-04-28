/**
 * Tests unitaires pour stores/reservationStore.ts
 * Machine d'états réservation (14 états) + CRUD liste
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useReservationStore, canReservationTransition, assertReservationTransition } from '../reservationStore'

beforeEach(() => {
  useReservationStore.getState().reset()
})

// ─── Machine d'états ──────────────────────────────────────────────────────────

describe('reservationStore - canReservationTransition', () => {
  it('draft → confirmed : autorisé', () => {
    expect(canReservationTransition('draft', 'confirmed')).toBe(true)
  })

  it('draft → cancelled : autorisé', () => {
    expect(canReservationTransition('draft', 'cancelled')).toBe(true)
  })

  it('confirmed → pre_check : autorisé', () => {
    expect(canReservationTransition('confirmed', 'pre_check')).toBe(true)
  })

  it('pre_check → delivered : autorisé', () => {
    expect(canReservationTransition('pre_check', 'delivered')).toBe(true)
  })

  it('delivered → returned : autorisé', () => {
    expect(canReservationTransition('delivered', 'returned')).toBe(true)
  })

  it('extended → returned : autorisé', () => {
    expect(canReservationTransition('extended', 'returned')).toBe(true)
  })

  it('returned → completed : autorisé', () => {
    expect(canReservationTransition('returned', 'completed')).toBe(true)
  })

  it('completed → * : aucune transition', () => {
    expect(canReservationTransition('completed', 'cancelled')).toBe(false)
    expect(canReservationTransition('completed', 'draft')).toBe(false)
  })

  it('cancelled → * : aucune transition', () => {
    expect(canReservationTransition('cancelled', 'draft')).toBe(false)
  })

  it('draft → delivered : interdit (saute des étapes)', () => {
    expect(canReservationTransition('draft', 'delivered')).toBe(false)
  })
})

describe('reservationStore - assertReservationTransition', () => {
  it('ne throw pas si transition valide', () => {
    expect(() => assertReservationTransition('draft', 'confirmed')).not.toThrow()
  })

  it('throw si transition invalide', () => {
    expect(() => assertReservationTransition('completed', 'cancelled'))
      .toThrow('Transition invalide : completed → cancelled')
  })
})

describe('reservationStore - canTransition via store', () => {
  it('canTransition délègue à canReservationTransition', () => {
    expect(useReservationStore.getState().canTransition('draft', 'confirmed')).toBe(true)
    expect(useReservationStore.getState().canTransition('completed', 'cancelled')).toBe(false)
  })
})

// ─── CRUD liste ───────────────────────────────────────────────────────────────

describe('reservationStore - setList', () => {
  it('remplace la liste et le total', () => {
    useReservationStore.getState().setList(
      [{ id: 1, reference: 'RES-001' } as any, { id: 2, reference: 'RES-002' } as any],
      100
    )
    expect(useReservationStore.getState().list).toHaveLength(2)
    expect(useReservationStore.getState().total).toBe(100)
  })
})

describe('reservationStore - upsertListItem', () => {
  it('insère en tête si absent', () => {
    useReservationStore.getState().setList([{ id: 1 } as any], 1)
    useReservationStore.getState().upsertListItem({ id: 2 } as any)

    expect(useReservationStore.getState().list[0].id).toBe(2)
    expect(useReservationStore.getState().total).toBe(2)
  })

  it('met à jour en place si présent', () => {
    useReservationStore.getState().setList([{ id: 1, status: 'draft' } as any], 1)
    useReservationStore.getState().upsertListItem({ id: 1, status: 'confirmed' } as any)

    expect(useReservationStore.getState().list).toHaveLength(1)
    expect(useReservationStore.getState().list[0].status).toBe('confirmed')
    expect(useReservationStore.getState().total).toBe(1)
  })
})

describe('reservationStore - removeListItem', () => {
  it('supprime la réservation et efface selectedId si correspondant', () => {
    useReservationStore.getState().setList([{ id: 1 } as any, { id: 2 } as any], 2)
    useReservationStore.getState().setSelectedId(1)

    useReservationStore.getState().removeListItem(1)

    expect(useReservationStore.getState().list).toHaveLength(1)
    expect(useReservationStore.getState().selectedId).toBeNull()
    expect(useReservationStore.getState().total).toBe(1)
  })

  it('préserve selectedId si ce n\'est pas l\'id supprimé', () => {
    useReservationStore.getState().setList([{ id: 1 } as any, { id: 2 } as any], 2)
    useReservationStore.getState().setSelectedId(2)

    useReservationStore.getState().removeListItem(1)

    expect(useReservationStore.getState().selectedId).toBe(2) // préservé
  })

  it('efface detail si correspond à l\'id supprimé', () => {
    useReservationStore.getState().setDetail({ id: 5 } as any)
    useReservationStore.getState().removeListItem(5)
    expect(useReservationStore.getState().detail).toBeNull()
  })
})

// ─── setDetail / setDetailLoading ─────────────────────────────────────────────

describe('reservationStore - setDetail / setDetailLoading', () => {
  it('setDetail stocke le détail', () => {
    useReservationStore.getState().setDetail({ id: 10, reference: 'RES-010' } as any)
    expect(useReservationStore.getState().detail?.id).toBe(10)
  })

  it('setDetailLoading change le flag', () => {
    useReservationStore.getState().setDetailLoading(true)
    expect(useReservationStore.getState().detailLoading).toBe(true)
  })
})

// ─── reset ────────────────────────────────────────────────────────────────────

describe('reservationStore - reset', () => {
  it('remet tout à zéro', () => {
    useReservationStore.getState().setList([{ id: 1 } as any], 1)
    useReservationStore.getState().setSelectedId(1)
    useReservationStore.getState().setDetail({ id: 1 } as any)

    useReservationStore.getState().reset()

    const state = useReservationStore.getState()
    expect(state.list).toHaveLength(0)
    expect(state.total).toBe(0)
    expect(state.selectedId).toBeNull()
    expect(state.detail).toBeNull()
  })
})
