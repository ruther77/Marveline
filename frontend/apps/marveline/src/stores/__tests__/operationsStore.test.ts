/**
 * Tests unitaires pour stores/operationsStore.ts
 * Zustand persist — checklist terrain, QR codes, dommages, signature
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useOperationsStore } from '../operationsStore'

beforeEach(() => {
  useOperationsStore.getState().reset()
})

// ─── État initial ─────────────────────────────────────────────────────────────

describe('operationsStore - état initial', () => {
  it('tout à null/vide par défaut', () => {
    const state = useOperationsStore.getState()
    expect(state.departureInventory).toBeNull()
    expect(state.returnInventory).toBeNull()
    expect(state.activeReservationId).toBeNull()
    expect(state.scannedCodes).toHaveLength(0)
    expect(state.damageDeclarations).toHaveLength(0)
    expect(state.signature).toBeNull()
  })
})

// ─── Departure inventory ──────────────────────────────────────────────────────

describe('operationsStore - setDepartureInventory', () => {
  it('stocke l\'inventaire de départ', () => {
    const inv = { reservation_id: 1, items: [{ line_id: 10, quantity_expected: 3 }] } as any
    useOperationsStore.getState().setDepartureInventory(inv)
    expect(useOperationsStore.getState().departureInventory?.reservation_id).toBe(1)
  })

  it('accepte null pour réinitialiser', () => {
    useOperationsStore.getState().setDepartureInventory({ reservation_id: 1, items: [] } as any)
    useOperationsStore.getState().setDepartureInventory(null)
    expect(useOperationsStore.getState().departureInventory).toBeNull()
  })
})

describe('operationsStore - updateDepartureItem', () => {
  it('met à jour un item par line_id', () => {
    useOperationsStore.getState().setDepartureInventory({
      reservation_id: 1,
      items: [
        { line_id: 10, quantity_expected: 3, quantity_loaded: 0 },
        { line_id: 11, quantity_expected: 2, quantity_loaded: 0 },
      ],
    } as any)

    useOperationsStore.getState().updateDepartureItem(10, { quantity_loaded: 3 })

    const items = useOperationsStore.getState().departureInventory!.items!
    expect(items[0].quantity_loaded).toBe(3)
    expect(items[1].quantity_loaded).toBe(0) // non modifié
  })

  it('ne plante pas si departureInventory est null', () => {
    expect(() =>
      useOperationsStore.getState().updateDepartureItem(99, { quantity_loaded: 1 })
    ).not.toThrow()
  })
})

describe('operationsStore - setDepartureLoading', () => {
  it('change le flag', () => {
    useOperationsStore.getState().setDepartureLoading(true)
    expect(useOperationsStore.getState().departureLoading).toBe(true)
  })
})

// ─── Return inventory ─────────────────────────────────────────────────────────

describe('operationsStore - setReturnInventory', () => {
  it('stocke l\'inventaire de retour', () => {
    const inv = { reservation_id: 2, items: [] } as any
    useOperationsStore.getState().setReturnInventory(inv)
    expect(useOperationsStore.getState().returnInventory?.reservation_id).toBe(2)
  })
})

// ─── Réservation active ───────────────────────────────────────────────────────

describe('operationsStore - setActiveReservationId', () => {
  it('stocke l\'id actif', () => {
    useOperationsStore.getState().setActiveReservationId(42)
    expect(useOperationsStore.getState().activeReservationId).toBe(42)
  })
})

// ─── QR codes scannés ─────────────────────────────────────────────────────────

describe('operationsStore - addScannedCode', () => {
  it('ajoute un code QR', () => {
    useOperationsStore.getState().addScannedCode('QR-TABLE-001')
    expect(useOperationsStore.getState().scannedCodes).toContain('QR-TABLE-001')
  })

  it('ne dédouble pas un code déjà scanné', () => {
    useOperationsStore.getState().addScannedCode('QR-TABLE-001')
    useOperationsStore.getState().addScannedCode('QR-TABLE-001')
    expect(useOperationsStore.getState().scannedCodes).toHaveLength(1)
  })

  it('accepte plusieurs codes différents', () => {
    useOperationsStore.getState().addScannedCode('CODE-A')
    useOperationsStore.getState().addScannedCode('CODE-B')
    expect(useOperationsStore.getState().scannedCodes).toHaveLength(2)
  })
})

// ─── Déclarations de dommages ─────────────────────────────────────────────────

describe('operationsStore - markDamaged / removeDamage', () => {
  it('ajoute une déclaration de dommage', () => {
    useOperationsStore.getState().markDamaged({ product_id: 1, severity: 'minor' } as any)
    expect(useOperationsStore.getState().damageDeclarations).toHaveLength(1)
  })

  it('remplace si même product_id (mise à jour)', () => {
    useOperationsStore.getState().markDamaged({ product_id: 1, severity: 'minor' } as any)
    useOperationsStore.getState().markDamaged({ product_id: 1, severity: 'major' } as any)

    const declarations = useOperationsStore.getState().damageDeclarations
    expect(declarations).toHaveLength(1) // pas de doublon
    expect(declarations[0].severity).toBe('major')
  })

  it('removeDamage supprime par product_id', () => {
    useOperationsStore.getState().markDamaged({ product_id: 1, severity: 'minor' } as any)
    useOperationsStore.getState().markDamaged({ product_id: 2, severity: 'major' } as any)

    useOperationsStore.getState().removeDamage(1)

    const declarations = useOperationsStore.getState().damageDeclarations
    expect(declarations).toHaveLength(1)
    expect(declarations[0].product_id).toBe(2)
  })
})

// ─── Signature ────────────────────────────────────────────────────────────────

describe('operationsStore - setSignature', () => {
  it('stocke la signature base64', () => {
    useOperationsStore.getState().setSignature('data:image/png;base64,abc123')
    expect(useOperationsStore.getState().signature).toBe('data:image/png;base64,abc123')
  })

  it('accepte null pour effacer la signature', () => {
    useOperationsStore.getState().setSignature('data:image/png;base64,abc')
    useOperationsStore.getState().setSignature(null)
    expect(useOperationsStore.getState().signature).toBeNull()
  })
})

// ─── clearSession ─────────────────────────────────────────────────────────────

describe('operationsStore - clearSession', () => {
  it('vide la session terrain sans toucher les données persistées', () => {
    useOperationsStore.getState().setActiveReservationId(99)
    useOperationsStore.getState().addScannedCode('CODE-X')
    useOperationsStore.getState().markDamaged({ product_id: 5 } as any)
    useOperationsStore.getState().setSignature('data:...')
    useOperationsStore.getState().setDepartureInventory({ reservation_id: 99 } as any)

    useOperationsStore.getState().clearSession()

    const state = useOperationsStore.getState()
    expect(state.scannedCodes).toHaveLength(0)
    expect(state.damageDeclarations).toHaveLength(0)
    expect(state.signature).toBeNull()
    expect(state.activeReservationId).toBeNull()
    expect(state.departureInventory).toBeNull()
  })
})

// ─── reset ────────────────────────────────────────────────────────────────────

describe('operationsStore - reset', () => {
  it('remet tout à l\'état initial', () => {
    useOperationsStore.getState().setActiveReservationId(10)
    useOperationsStore.getState().addScannedCode('QR-A')
    useOperationsStore.getState().setDepartureLoading(true)

    useOperationsStore.getState().reset()

    const state = useOperationsStore.getState()
    expect(state.activeReservationId).toBeNull()
    expect(state.scannedCodes).toHaveLength(0)
    expect(state.departureLoading).toBe(false)
  })
})
