/**
 * Tests unitaires pour stores/eventStore.ts
 * Machine d'états événement + CRUD liste
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useEventStore, canEventTransition, assertEventTransition } from '../eventStore'

beforeEach(() => {
  useEventStore.getState().reset()
})

// ─── Machine d'états ──────────────────────────────────────────────────────────

describe('eventStore - canEventTransition', () => {
  it('planned → in_progress : autorisé', () => {
    expect(canEventTransition('planned', 'in_progress')).toBe(true)
  })

  it('planned → risk : autorisé', () => {
    expect(canEventTransition('planned', 'risk')).toBe(true)
  })

  it('planned → cancelled : autorisé', () => {
    expect(canEventTransition('planned', 'cancelled')).toBe(true)
  })

  it('risk → planned : autorisé (retour possible)', () => {
    expect(canEventTransition('risk', 'planned')).toBe(true)
  })

  it('in_progress → incident : autorisé', () => {
    expect(canEventTransition('in_progress', 'incident')).toBe(true)
  })

  it('in_progress → returned : autorisé', () => {
    expect(canEventTransition('in_progress', 'returned')).toBe(true)
  })

  it('returned → damage : autorisé', () => {
    expect(canEventTransition('returned', 'damage')).toBe(true)
  })

  it('returned → closed : autorisé', () => {
    expect(canEventTransition('returned', 'closed')).toBe(true)
  })

  it('damage → closed : autorisé', () => {
    expect(canEventTransition('damage', 'closed')).toBe(true)
  })

  it('cancelled → * : aucune transition', () => {
    expect(canEventTransition('cancelled', 'planned')).toBe(false)
    expect(canEventTransition('cancelled', 'in_progress')).toBe(false)
  })

  it('closed → * : aucune transition', () => {
    expect(canEventTransition('closed', 'planned')).toBe(false)
  })

  it('état inconnu → false', () => {
    expect(canEventTransition('unknown', 'planned')).toBe(false)
  })
})

describe('eventStore - assertEventTransition', () => {
  it('ne throw pas si transition valide', () => {
    expect(() => assertEventTransition('planned', 'in_progress')).not.toThrow()
  })

  it('throw si transition invalide', () => {
    expect(() => assertEventTransition('closed', 'planned'))
      .toThrow('Transition invalide : closed → planned')
  })
})

// ─── CRUD liste ───────────────────────────────────────────────────────────────

describe('eventStore - setList / upsertListItem / removeListItem', () => {
  it('setList remplace tout', () => {
    useEventStore.getState().setList(
      [{ id: 1, status: 'planned' } as any, { id: 2, status: 'risk' } as any],
      20
    )
    expect(useEventStore.getState().list).toHaveLength(2)
    expect(useEventStore.getState().total).toBe(20)
  })

  it('upsertListItem insère en tête si absent', () => {
    useEventStore.getState().setList([{ id: 1 } as any], 1)
    useEventStore.getState().upsertListItem({ id: 2, status: 'planned' } as any)

    expect(useEventStore.getState().list[0].id).toBe(2)
    expect(useEventStore.getState().total).toBe(2)
  })

  it('upsertListItem met à jour en place', () => {
    useEventStore.getState().setList([{ id: 1, status: 'planned' } as any], 1)
    useEventStore.getState().upsertListItem({ id: 1, status: 'in_progress' } as any)

    expect(useEventStore.getState().list).toHaveLength(1)
    expect(useEventStore.getState().list[0].status).toBe('in_progress')
    expect(useEventStore.getState().total).toBe(1)
  })

  it('removeListItem supprime, décrémente, efface selectedId', () => {
    useEventStore.getState().setList([{ id: 1 } as any, { id: 2 } as any], 2)
    useEventStore.getState().setSelectedId(1)

    useEventStore.getState().removeListItem(1)

    expect(useEventStore.getState().list).toHaveLength(1)
    expect(useEventStore.getState().total).toBe(1)
    expect(useEventStore.getState().selectedId).toBeNull()
  })

  it('removeListItem préserve selectedId si différent', () => {
    useEventStore.getState().setList([{ id: 1 } as any, { id: 2 } as any], 2)
    useEventStore.getState().setSelectedId(2)

    useEventStore.getState().removeListItem(1)

    expect(useEventStore.getState().selectedId).toBe(2)
  })

  it('removeListItem efface detail si correspond', () => {
    useEventStore.getState().setDetail({ id: 5, status: 'planned' } as any)
    useEventStore.getState().removeListItem(5)
    expect(useEventStore.getState().detail).toBeNull()
  })
})

// ─── reset ────────────────────────────────────────────────────────────────────

describe('eventStore - reset', () => {
  it('remet tout à zéro', () => {
    useEventStore.getState().setList([{ id: 1 } as any], 1)
    useEventStore.getState().setSelectedId(1)
    useEventStore.getState().setDetailLoading(true)

    useEventStore.getState().reset()

    expect(useEventStore.getState().list).toHaveLength(0)
    expect(useEventStore.getState().selectedId).toBeNull()
    expect(useEventStore.getState().detailLoading).toBe(false)
  })
})
