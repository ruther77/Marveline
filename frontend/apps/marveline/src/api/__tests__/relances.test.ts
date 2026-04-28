/**
 * Tests unitaires pour api/relances.ts
 * Vérifie list (avec filtres), schedule, cancel, markSent
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { relancesApi, type RelanceResponse } from '../relances'
import { api } from '../fetchClient'

vi.mock('../fetchClient', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  fetchBlob: vi.fn(),
  fetchFormData: vi.fn(),
}))

const mockRelance: RelanceResponse = {
  id: 1,
  tenant_id: 1,
  invoice_id: 42,
  scheduled_at: '2026-03-15T09:00:00',
  sent_at: null,
  cancelled_at: null,
  status: 'scheduled',
  channel: 'email',
  message: 'Rappel de paiement pour la facture FAC-0042',
  created_at: '2026-03-10T10:00:00',
}

describe('relancesApi - list', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère toutes les relances sans filtre', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [mockRelance], total: 1, skip: 0, limit: 20 })

    const result = await relancesApi.list()

    expect(api.get).toHaveBeenCalledWith('/relances')
    expect(result.items).toHaveLength(1)
    expect(result.items[0].invoice_id).toBe(42)
  })

  it('filtre par invoice_id', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [mockRelance], total: 1, skip: 0, limit: 20 })

    await relancesApi.list({ invoice_id: 42 })

    expect(api.get).toHaveBeenCalledWith('/relances?invoice_id=42')
  })

  it('filtre par customer_id', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, skip: 0, limit: 20 })

    await relancesApi.list({ customer_id: 10 })

    expect(api.get).toHaveBeenCalledWith('/relances?customer_id=10')
  })

  it('combine invoice_id et customer_id', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, skip: 0, limit: 20 })

    await relancesApi.list({ invoice_id: 42, customer_id: 10 })

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).toContain('invoice_id=42')
    expect(url).toContain('customer_id=10')
  })

  it('gère liste vide', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, skip: 0, limit: 20 })
    const result = await relancesApi.list()
    expect(result.items).toHaveLength(0)
  })
})

describe('relancesApi - schedule', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('planifie une nouvelle relance', async () => {
    vi.mocked(api.post).mockResolvedValue(mockRelance)

    const result = await relancesApi.schedule({
      invoice_id: 42,
      scheduled_at: '2026-03-15T09:00:00',
      channel: 'email',
      message: 'Rappel de paiement',
    })

    expect(api.post).toHaveBeenCalledWith('/relances/schedule', expect.any(Object))
    expect(result.status).toBe('scheduled')
  })

  it('planifie avec channel par défaut (email)', async () => {
    vi.mocked(api.post).mockResolvedValue(mockRelance)

    await relancesApi.schedule({ invoice_id: 42, scheduled_at: '2026-03-15T09:00:00' })

    expect(api.post).toHaveBeenCalledWith('/relances/schedule', {
      invoice_id: 42,
      scheduled_at: '2026-03-15T09:00:00',
    })
  })
})

describe('relancesApi - cancel', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('annule une relance planifiée', async () => {
    const cancelled = { ...mockRelance, status: 'cancelled' as const, cancelled_at: '2026-03-11T10:00:00' }
    vi.mocked(api.post).mockResolvedValue(cancelled)

    const result = await relancesApi.cancel(1)

    expect(api.post).toHaveBeenCalledWith('/relances/cancel/1', {})
    expect(result.status).toBe('cancelled')
  })
})

describe('relancesApi - markSent', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('marque une relance comme envoyée', async () => {
    const sent = { ...mockRelance, status: 'sent' as const, sent_at: '2026-03-15T09:05:00' }
    vi.mocked(api.post).mockResolvedValue(sent)

    const result = await relancesApi.markSent(1)

    expect(api.post).toHaveBeenCalledWith('/relances/mark-sent/1', {})
    expect(result.status).toBe('sent')
    expect(result.sent_at).toBeTruthy()
  })
})
