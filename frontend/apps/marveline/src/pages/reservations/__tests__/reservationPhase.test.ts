/**
 * Tests unitaires pour derivePhase et les selectors de reservationPhase.
 * Couvre les 10 statuts de réservation et les branchements confirmed/draft.
 */
import { describe, it, expect } from 'vitest'
import { derivePhase } from '../ReservationRouter'
import {
  isDepositOk,
  isSignatureOk,
  isReadyForDelivery,
  isTerminal,
  canCloseReservation,
  canExtendReservation,
  hasLines,
} from '../selectors/reservationPhase'
import type { ReservationDetail, ReservationStatus } from '@/types/reservation'
import type { Deposit } from '@/types/deposit'

const mkReservation = (
  overrides: Partial<ReservationDetail> = {},
): ReservationDetail => ({
  id: 1,
  tenant_id: 1,
  status: 'draft' as ReservationStatus,
  customer_id: 1,
  delivery_date: '2026-05-01',
  event_date: '2026-05-02',
  return_date: '2026-05-03',
  total_amount_cents: 100000,
  lines: [],
  deposit_paid: false,
  signature_url: undefined,
  created_at: '2026-04-01',
  updated_at: '2026-04-01',
  ...overrides,
}) as ReservationDetail

const mkDeposit = (overrides: Partial<Deposit> = {}): Deposit => ({
  id: 1,
  reservation_id: 1,
  amount_cents: 20000,
  status: 'held',
  method: 'card',
  created_at: '2026-04-01',
  ...overrides,
}) as Deposit

const mkLine = (id = 1) => ({
  id,
  reservation_id: 1,
  product_id: 1,
  quantity: 1,
  unit_price_cents: 1000,
  subtotal_cents: 1000,
}) as ReservationDetail['lines'][number]

// ── selectors ───────────────────────────────────────────────────────────────

describe('isDepositOk', () => {
  it('true si deposit_paid=true', () => {
    expect(isDepositOk({ deposit_paid: true }, [])).toBe(true)
  })

  it('true si au moins un dépôt en status held', () => {
    expect(isDepositOk({ deposit_paid: false }, [mkDeposit({ status: 'held' })])).toBe(true)
  })

  it('false si aucun dépôt held et deposit_paid=false', () => {
    expect(isDepositOk({ deposit_paid: false }, [mkDeposit({ status: 'pending' })])).toBe(false)
    expect(isDepositOk({ deposit_paid: false }, [])).toBe(false)
    expect(isDepositOk({ deposit_paid: false }, undefined)).toBe(false)
  })
})

describe('isSignatureOk', () => {
  it('true si signature_url présente', () => {
    expect(isSignatureOk({ signature_url: 'https://cdn/sig.png' })).toBe(true)
  })

  it('false si signature_url vide ou null', () => {
    expect(isSignatureOk({ signature_url: undefined })).toBe(false)
    expect(isSignatureOk({ signature_url: '' })).toBe(false)
  })
})

describe('isReadyForDelivery', () => {
  it('true si status=confirmed + deposit OK + signature OK', () => {
    const r = { status: 'confirmed' as ReservationStatus, deposit_paid: true, signature_url: 'sig' }
    expect(isReadyForDelivery(r, [])).toBe(true)
  })

  it('false si manque signature', () => {
    const r = { status: 'confirmed' as ReservationStatus, deposit_paid: true, signature_url: undefined }
    expect(isReadyForDelivery(r, [])).toBe(false)
  })

  it('false si manque dépôt', () => {
    const r = { status: 'confirmed' as ReservationStatus, deposit_paid: false, signature_url: 'sig' }
    expect(isReadyForDelivery(r, [])).toBe(false)
  })

  it('false si status != confirmed', () => {
    const r = { status: 'draft' as ReservationStatus, deposit_paid: true, signature_url: 'sig' }
    expect(isReadyForDelivery(r, [])).toBe(false)
  })
})

describe('isTerminal', () => {
  it('true sur completed et cancelled', () => {
    expect(isTerminal({ status: 'completed' })).toBe(true)
    expect(isTerminal({ status: 'cancelled' })).toBe(true)
  })

  it('false sur tous les autres statuts', () => {
    expect(isTerminal({ status: 'draft' })).toBe(false)
    expect(isTerminal({ status: 'confirmed' })).toBe(false)
    expect(isTerminal({ status: 'delivered' })).toBe(false)
  })
})

describe('canCloseReservation', () => {
  it('true seulement sur returned', () => {
    expect(canCloseReservation({ status: 'returned' })).toBe(true)
    expect(canCloseReservation({ status: 'returned_dispute' })).toBe(false)
    expect(canCloseReservation({ status: 'delivered' })).toBe(false)
  })
})

describe('canExtendReservation', () => {
  it('true sur delivered et extended', () => {
    expect(canExtendReservation({ status: 'delivered' })).toBe(true)
    expect(canExtendReservation({ status: 'extended' })).toBe(true)
  })

  it('false partout ailleurs', () => {
    expect(canExtendReservation({ status: 'returned' })).toBe(false)
    expect(canExtendReservation({ status: 'confirmed' })).toBe(false)
  })
})

describe('hasLines', () => {
  it('true si au moins une ligne', () => {
    expect(hasLines({ lines: [mkLine()] })).toBe(true)
  })

  it('false si tableau vide ou undefined', () => {
    expect(hasLines({ lines: [] })).toBe(false)
    expect(hasLines({ lines: undefined as never })).toBe(false)
  })
})

// ── derivePhase ─────────────────────────────────────────────────────────────

describe('derivePhase', () => {
  it('cancelled → annulee', () => {
    expect(derivePhase(mkReservation({ status: 'cancelled' }), [])).toBe('annulee')
  })

  it('completed → terminee', () => {
    expect(derivePhase(mkReservation({ status: 'completed' }), [])).toBe('terminee')
  })

  it('returned_dispute → litige', () => {
    expect(derivePhase(mkReservation({ status: 'returned_dispute' }), [])).toBe('litige')
  })

  it('returned → retournee', () => {
    expect(derivePhase(mkReservation({ status: 'returned' }), [])).toBe('retournee')
  })

  it('extended → prolongee', () => {
    expect(derivePhase(mkReservation({ status: 'extended' }), [])).toBe('prolongee')
  })

  it('delivered → en-cours', () => {
    expect(derivePhase(mkReservation({ status: 'delivered' }), [])).toBe('en-cours')
  })

  it('confirmed_risk → risque', () => {
    expect(derivePhase(mkReservation({ status: 'confirmed_risk' }), [])).toBe('risque')
  })

  it('pre_check → precheck', () => {
    expect(derivePhase(mkReservation({ status: 'pre_check' }), [])).toBe('precheck')
  })

  describe('confirmed', () => {
    it('→ prete si dépôt + signature OK', () => {
      const r = mkReservation({ status: 'confirmed', deposit_paid: true, signature_url: 'sig' })
      expect(derivePhase(r, [])).toBe('prete')
    })

    it('→ prete si dépôt via deposits.held + signature OK', () => {
      const r = mkReservation({ status: 'confirmed', deposit_paid: false, signature_url: 'sig' })
      expect(derivePhase(r, [mkDeposit({ status: 'held' })])).toBe('prete')
    })

    it('→ legal si manque signature', () => {
      const r = mkReservation({ status: 'confirmed', deposit_paid: true, signature_url: undefined })
      expect(derivePhase(r, [])).toBe('legal')
    })

    it('→ legal si manque dépôt', () => {
      const r = mkReservation({ status: 'confirmed', deposit_paid: false, signature_url: 'sig' })
      expect(derivePhase(r, [])).toBe('legal')
    })

    it('→ legal si rien', () => {
      expect(derivePhase(mkReservation({ status: 'confirmed' }), [])).toBe('legal')
    })
  })

  describe('draft', () => {
    it('→ brouillon-incomplet si lines vide', () => {
      expect(derivePhase(mkReservation({ status: 'draft', lines: [] }), [])).toBe('brouillon-incomplet')
    })

    it('→ brouillon si au moins une ligne', () => {
      expect(derivePhase(mkReservation({ status: 'draft', lines: [mkLine()] }), [])).toBe('brouillon')
    })
  })
})
