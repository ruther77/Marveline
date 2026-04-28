/**
 * Tests unitaires pour stores/devisStore.ts
 * Machine d'états devis + stepper + CRUD liste + buildDevisCreate
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useDevisStore, canDevisTransition, assertDevisTransition, buildDevisCreate } from '../devisStore'
import { useCartStore } from '../cartStore'

beforeEach(() => {
  useDevisStore.getState().reset()
  useCartStore.getState().reset()
})

// ─── État initial ─────────────────────────────────────────────────────────────

describe('devisStore - état initial', () => {
  it('liste vide, total 0, pas de sélection', () => {
    const { list, total, selectedId, detail, currentStep } = useDevisStore.getState()
    expect(list).toHaveLength(0)
    expect(total).toBe(0)
    expect(selectedId).toBeNull()
    expect(detail).toBeNull()
    expect(currentStep).toBe('client')
  })
})

// ─── Machine d'états ──────────────────────────────────────────────────────────

describe('devisStore - canDevisTransition', () => {
  it('draft → sent : autorisé', () => {
    expect(canDevisTransition('draft', 'sent')).toBe(true)
  })

  it('draft → accepted : interdit (pas direct)', () => {
    expect(canDevisTransition('draft', 'accepted')).toBe(false)
  })

  it('sent → accepted : autorisé', () => {
    expect(canDevisTransition('sent', 'accepted')).toBe(true)
  })

  it('accepted → converted : autorisé', () => {
    expect(canDevisTransition('accepted', 'converted')).toBe(true)
  })

  it('refused → * : aucune transition possible', () => {
    expect(canDevisTransition('refused', 'draft')).toBe(false)
    expect(canDevisTransition('refused', 'sent')).toBe(false)
  })

  it('état inconnu → false', () => {
    expect(canDevisTransition('unknown', 'sent')).toBe(false)
  })
})

describe('devisStore - assertDevisTransition', () => {
  it('ne throw pas si transition valide', () => {
    expect(() => assertDevisTransition('draft', 'sent')).not.toThrow()
  })

  it('throw si transition invalide', () => {
    expect(() => assertDevisTransition('refused', 'sent'))
      .toThrow('Transition invalide : refused → sent')
  })
})

// ─── CRUD liste ───────────────────────────────────────────────────────────────

describe('devisStore - setList', () => {
  it('remplace la liste et le total', () => {
    useDevisStore.getState().setList(
      [{ id: 1, reference: 'DEV-001' } as any, { id: 2, reference: 'DEV-002' } as any],
      50
    )
    expect(useDevisStore.getState().list).toHaveLength(2)
    expect(useDevisStore.getState().total).toBe(50)
  })
})

describe('devisStore - upsertListItem', () => {
  it('insère en tête si absent', () => {
    useDevisStore.getState().setList([{ id: 1, reference: 'DEV-001' } as any], 1)
    useDevisStore.getState().upsertListItem({ id: 2, reference: 'DEV-002' } as any)

    expect(useDevisStore.getState().list[0].id).toBe(2) // tête
    expect(useDevisStore.getState().total).toBe(2)
  })

  it('met à jour en place si déjà présent', () => {
    useDevisStore.getState().setList([{ id: 1, reference: 'DEV-001', status: 'draft' } as any], 1)
    useDevisStore.getState().upsertListItem({ id: 1, reference: 'DEV-001', status: 'sent' } as any)

    expect(useDevisStore.getState().list).toHaveLength(1) // pas de doublon
    expect(useDevisStore.getState().list[0].status).toBe('sent')
    expect(useDevisStore.getState().total).toBe(1) // pas incrémenté
  })
})

describe('devisStore - removeListItem', () => {
  it('supprime le devis, décrémente total, efface selectedId', () => {
    useDevisStore.getState().setList([{ id: 1 } as any, { id: 2 } as any], 2)
    useDevisStore.getState().setSelectedId(1)

    useDevisStore.getState().removeListItem(1)

    const state = useDevisStore.getState()
    expect(state.list).toHaveLength(1)
    expect(state.total).toBe(1)
    expect(state.selectedId).toBeNull() // effacé car c'était l'id supprimé
  })

  it('ne descend pas total sous 0', () => {
    useDevisStore.getState().setList([], 0)
    useDevisStore.getState().removeListItem(99)
    expect(useDevisStore.getState().total).toBe(0)
  })

  it('efface detail si c\'est le devis supprimé', () => {
    useDevisStore.getState().setDetail({ id: 3 } as any)
    useDevisStore.getState().removeListItem(3)
    expect(useDevisStore.getState().detail).toBeNull()
  })
})

// ─── Stepper ──────────────────────────────────────────────────────────────────

describe('devisStore - stepper', () => {
  it('setStep change l\'étape directement', () => {
    useDevisStore.getState().setStep('recap')
    expect(useDevisStore.getState().currentStep).toBe('recap')
  })

  it('nextStep client → articles → recap', () => {
    useDevisStore.getState().nextStep()
    expect(useDevisStore.getState().currentStep).toBe('articles')

    useDevisStore.getState().nextStep()
    expect(useDevisStore.getState().currentStep).toBe('recap')
  })

  it('nextStep s\'arrête à recap (dernière étape)', () => {
    useDevisStore.getState().setStep('recap')
    useDevisStore.getState().nextStep()
    expect(useDevisStore.getState().currentStep).toBe('recap')
  })

  it('prevStep recap → articles → client', () => {
    useDevisStore.getState().setStep('recap')
    useDevisStore.getState().prevStep()
    expect(useDevisStore.getState().currentStep).toBe('articles')

    useDevisStore.getState().prevStep()
    expect(useDevisStore.getState().currentStep).toBe('client')
  })

  it('prevStep s\'arrête à client (première étape)', () => {
    useDevisStore.getState().prevStep()
    expect(useDevisStore.getState().currentStep).toBe('client')
  })
})

// ─── buildDevisCreate ─────────────────────────────────────────────────────────

describe('buildDevisCreate', () => {
  it('assemble les données depuis cartStore', () => {
    useCartStore.getState().setCustomer(42)
    useCartStore.getState().setEventInfo({ event_date: '2026-06-15', event_location: 'Lyon' })
    useCartStore.getState().setNotes('Notes test')
    useCartStore.getState().addLine({
      product_id: 1,
      product_name: 'Table',
      quantity: 2,
      unit_price_cents: 1500,
      available_quantity: 10,
    })

    const payload = buildDevisCreate()

    expect(payload.customer_id).toBe(42)
    expect(payload.event_date).toBe('2026-06-15')
    expect(payload.event_location).toBe('Lyon')
    expect(payload.notes).toBe('Notes test')
    expect(payload.lines).toHaveLength(1)
    expect(payload.lines[0].product_id).toBe(1)
    expect(payload.lines[0].quantity).toBe(2)
    expect(payload.lines[0].unit_price_cents).toBe(1500)
  })

  it('retourne panier vide si aucun article', () => {
    const payload = buildDevisCreate()
    expect(payload.lines).toHaveLength(0)
    expect(payload.customer_id).toBeNull()
  })
})

// ─── reset ────────────────────────────────────────────────────────────────────

describe('devisStore - reset', () => {
  it('remet tout à zéro dont le cartStore', () => {
    useDevisStore.getState().setList([{ id: 1 } as any], 1)
    useDevisStore.getState().setStep('articles')
    useCartStore.getState().setCustomer(5)

    useDevisStore.getState().reset()

    expect(useDevisStore.getState().list).toHaveLength(0)
    expect(useDevisStore.getState().currentStep).toBe('client')
    expect(useCartStore.getState().customer_id).toBeNull() // cart aussi réinitialisé
  })
})
