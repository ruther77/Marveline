/**
 * Tests unitaires pour stores/invoiceStore.ts
 * Machine d'états facture + paymentDraft (calcul centimes) + CRUD liste
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useInvoiceStore, canInvoiceTransition, assertInvoiceTransition } from '../invoiceStore'

beforeEach(() => {
  useInvoiceStore.getState().reset()
})

// ─── Machine d'états ──────────────────────────────────────────────────────────

describe('invoiceStore - canInvoiceTransition', () => {
  it('draft → sent : autorisé', () => {
    expect(canInvoiceTransition('draft', 'sent')).toBe(true)
  })

  it('draft → cancelled : autorisé', () => {
    expect(canInvoiceTransition('draft', 'cancelled')).toBe(true)
  })

  it('sent → paid : autorisé', () => {
    expect(canInvoiceTransition('sent', 'paid')).toBe(true)
  })

  it('sent → overdue : autorisé', () => {
    expect(canInvoiceTransition('sent', 'overdue')).toBe(true)
  })

  it('overdue → paid : autorisé', () => {
    expect(canInvoiceTransition('overdue', 'paid')).toBe(true)
  })

  it('paid → * : aucune transition', () => {
    expect(canInvoiceTransition('paid', 'sent')).toBe(false)
    expect(canInvoiceTransition('paid', 'cancelled')).toBe(false)
  })

  it('cancelled → * : aucune transition', () => {
    expect(canInvoiceTransition('cancelled', 'draft')).toBe(false)
  })

  it('état inconnu → false', () => {
    expect(canInvoiceTransition('unknown', 'sent')).toBe(false)
  })
})

describe('invoiceStore - assertInvoiceTransition', () => {
  it('ne throw pas si transition valide', () => {
    expect(() => assertInvoiceTransition('draft', 'sent')).not.toThrow()
  })

  it('throw si transition invalide', () => {
    expect(() => assertInvoiceTransition('paid', 'draft'))
      .toThrow('Transition invalide : paid → draft')
  })
})

// ─── CRUD liste ───────────────────────────────────────────────────────────────

describe('invoiceStore - setList / upsertListItem / removeListItem', () => {
  it('setList remplace tout', () => {
    useInvoiceStore.getState().setList(
      [{ id: 1, invoice_number: 'INV-001' } as any],
      42
    )
    expect(useInvoiceStore.getState().list).toHaveLength(1)
    expect(useInvoiceStore.getState().total).toBe(42)
  })

  it('upsertListItem insère en tête si absent', () => {
    useInvoiceStore.getState().setList([{ id: 1 } as any], 1)
    useInvoiceStore.getState().upsertListItem({ id: 2, status: 'draft' } as any)

    expect(useInvoiceStore.getState().list[0].id).toBe(2)
    expect(useInvoiceStore.getState().total).toBe(2)
  })

  it('upsertListItem met à jour en place', () => {
    useInvoiceStore.getState().setList([{ id: 1, status: 'draft' } as any], 1)
    useInvoiceStore.getState().upsertListItem({ id: 1, status: 'sent' } as any)

    expect(useInvoiceStore.getState().list).toHaveLength(1)
    expect(useInvoiceStore.getState().list[0].status).toBe('sent')
  })

  it('removeListItem supprime et décrémente', () => {
    useInvoiceStore.getState().setList([{ id: 1 } as any, { id: 2 } as any], 2)
    useInvoiceStore.getState().setSelectedId(1)

    useInvoiceStore.getState().removeListItem(1)

    expect(useInvoiceStore.getState().list).toHaveLength(1)
    expect(useInvoiceStore.getState().selectedId).toBeNull()
    expect(useInvoiceStore.getState().total).toBe(1)
  })
})

describe('invoiceStore - setOverdueCount', () => {
  it('met à jour overdueCount', () => {
    useInvoiceStore.getState().setOverdueCount(7)
    expect(useInvoiceStore.getState().overdueCount).toBe(7)
  })
})

// ─── PaymentDraft ─────────────────────────────────────────────────────────────

describe('invoiceStore - updatePaymentDraft', () => {
  it('calcule amount_cents depuis amount_euros', () => {
    useInvoiceStore.getState().updatePaymentDraft({ amount_euros: '25.50' })
    expect(useInvoiceStore.getState().paymentDraft.amount_cents).toBe(2550)
  })

  it('arrondit correctement les centimes (ex: 1/3)', () => {
    useInvoiceStore.getState().updatePaymentDraft({ amount_euros: '33.333' })
    // Math.round(33.333 * 100) = 3333
    expect(useInvoiceStore.getState().paymentDraft.amount_cents).toBe(3333)
  })

  it('amount_cents = 0 si montant NaN', () => {
    useInvoiceStore.getState().updatePaymentDraft({ amount_euros: 'abc' })
    expect(useInvoiceStore.getState().paymentDraft.amount_cents).toBe(0)
  })

  it('amount_cents = 0 si montant négatif', () => {
    useInvoiceStore.getState().updatePaymentDraft({ amount_euros: '-10' })
    expect(useInvoiceStore.getState().paymentDraft.amount_cents).toBe(0)
  })

  it('met à jour payment_method sans toucher amount_euros', () => {
    useInvoiceStore.getState().updatePaymentDraft({ amount_euros: '100', payment_method: 'card' })
    useInvoiceStore.getState().updatePaymentDraft({ payment_method: 'cash' })

    const draft = useInvoiceStore.getState().paymentDraft
    expect(draft.payment_method).toBe('cash')
    expect(draft.amount_euros).toBe('100') // non modifié
    expect(draft.amount_cents).toBe(10000)
  })
})

describe('invoiceStore - clearPaymentDraft', () => {
  it('remet le draft aux valeurs par défaut', () => {
    useInvoiceStore.getState().updatePaymentDraft({ amount_euros: '500', payment_method: 'bank' })
    useInvoiceStore.getState().clearPaymentDraft()

    const draft = useInvoiceStore.getState().paymentDraft
    expect(draft.amount_euros).toBe('')
    expect(draft.amount_cents).toBe(0)
    expect(draft.payment_method).toBeNull()
  })
})

// ─── reset ────────────────────────────────────────────────────────────────────

describe('invoiceStore - reset', () => {
  it('remet tout à zéro', () => {
    useInvoiceStore.getState().setList([{ id: 1 } as any], 5)
    useInvoiceStore.getState().setOverdueCount(3)
    useInvoiceStore.getState().updatePaymentDraft({ amount_euros: '200' })

    useInvoiceStore.getState().reset()

    const state = useInvoiceStore.getState()
    expect(state.list).toHaveLength(0)
    expect(state.overdueCount).toBe(0)
    expect(state.paymentDraft.amount_euros).toBe('')
  })
})
