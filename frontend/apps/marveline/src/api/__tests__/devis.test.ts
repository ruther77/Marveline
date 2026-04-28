/**
 * Tests unitaires pour api/devis.ts
 * Vérifie CRUD devis + actions (send, accept, refuse, duplicate, renew)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { devisApi } from '../devis'
import { api, fetchBlob } from '../fetchClient'
import type { DevisListItem, DevisDetail, DevisDetailFull } from '@/types/devis'

// Mock fetchClient
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

const mockDevisItem: DevisListItem = {
  id: 1,
  reference: 'DEV-0001',
  status: 'draft',
  customer_id: 10,
  customer_name: 'Dupont SAS',
  total_ht_cents: 50000,
  total_ttc_cents: 60000,
  created_at: '2026-02-01T10:00:00',
  updated_at: '2026-02-01T10:00:00',
  expiry_date: null,
  sent_at: null,
  accepted_at: null,
}

describe('devisApi - listDevis', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère liste paginée par défaut', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [mockDevisItem], total: 1, skip: 0, limit: 20 })

    const result = await devisApi.listDevis()

    expect(api.get).toHaveBeenCalledWith(expect.stringContaining('/devis?'))
    expect(result.items).toHaveLength(1)
    expect(result.total).toBe(1)
    expect(result.skip).toBe(0)
    expect(result.limit).toBe(20)
  })

  it('applique les filtres status et customer_id', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, skip: 10, limit: 10 })

    await devisApi.listDevis({ status: 'sent', customer_id: 10, skip: 10, limit: 10 })

    const call = vi.mocked(api.get).mock.calls[0][0] as string
    expect(call).toContain('status=sent')
    expect(call).toContain('customer_id=10')
    expect(call).toContain('skip=10')
    expect(call).toContain('limit=10')
  })

  it('gère liste vide', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, skip: 0, limit: 20 })

    const result = await devisApi.listDevis()
    expect(result.items).toHaveLength(0)
    expect(result.total).toBe(0)
  })
})

describe('devisApi - get', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère un devis par ID', async () => {
    const mockFull = { ...mockDevisItem, modules: [], phases: [] } as unknown as DevisDetailFull
    vi.mocked(api.get).mockResolvedValue(mockFull)

    const result = await devisApi.get(1)

    expect(api.get).toHaveBeenCalledWith('/devis/1')
    expect(result.id).toBe(1)
  })

  it('propage les erreurs 404', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Devis introuvable'))
    await expect(devisApi.get(999)).rejects.toThrow('Devis introuvable')
  })
})

describe('devisApi - create', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('crée un nouveau devis', async () => {
    const mockDetail = { id: 2, reference: 'DEV-0002', status: 'draft' } as unknown as DevisDetail
    vi.mocked(api.post).mockResolvedValue(mockDetail)

    const result = await devisApi.create({ customer_id: 10, expiry_date: null })

    expect(api.post).toHaveBeenCalledWith('/devis', { customer_id: 10, expiry_date: null })
    expect(result.id).toBe(2)
  })
})

describe('devisApi - update', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('met à jour un devis (PATCH partiel)', async () => {
    const mockDetail = { id: 1, status: 'draft', notes: 'Mise à jour' } as unknown as DevisDetail
    vi.mocked(api.patch).mockResolvedValue(mockDetail)

    const result = await devisApi.update(1, { notes: 'Mise à jour' })

    expect(api.patch).toHaveBeenCalledWith('/devis/1', { notes: 'Mise à jour' })
    expect(result.id).toBe(1)
  })
})

describe('devisApi - send', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('envoie un devis au client', async () => {
    const mockSent = { id: 1, status: 'sent', sent_at: '2026-02-15T10:00:00' } as unknown as DevisDetail
    vi.mocked(api.post).mockResolvedValue(mockSent)

    const result = await devisApi.send(1)

    expect(api.post).toHaveBeenCalledWith('/devis/1/send')
    expect(result.status).toBe('sent')
  })
})

describe('devisApi - accept / refuse / cancel / duplicate / renew', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('accepte un devis', async () => {
    const mockAccepted = { id: 1, status: 'accepted' } as unknown as DevisDetail
    vi.mocked(api.post).mockResolvedValue(mockAccepted)

    const result = await devisApi.accept(1)

    expect(api.post).toHaveBeenCalledWith('/devis/1/accept')
    expect(result.status).toBe('accepted')
  })

  it('refuse un devis avec raison', async () => {
    const mockRefused = { id: 1, status: 'refused' } as unknown as DevisDetail
    vi.mocked(api.post).mockResolvedValue(mockRefused)

    await devisApi.refuse(1, 'Budget insuffisant')

    expect(api.post).toHaveBeenCalledWith('/devis/1/refuse', { reason: 'Budget insuffisant' })
  })

  it('annule un devis', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 1, status: 'cancelled' } as unknown as DevisDetail)

    await devisApi.cancel(1)

    expect(api.post).toHaveBeenCalledWith('/devis/1/cancel')
  })

  it('duplique un devis', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 2, status: 'draft' } as unknown as DevisDetail)

    const result = await devisApi.duplicate(1)

    expect(api.post).toHaveBeenCalledWith('/devis/1/duplicate')
    expect(result.id).toBe(2)
  })

  it('renouvelle un devis expiré', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 3, status: 'draft' } as unknown as DevisDetail)

    const result = await devisApi.renew(1)

    expect(api.post).toHaveBeenCalledWith('/devis/1/renew')
    expect(result.id).toBe(3)
    expect(result.status).toBe('draft')
  })
})

describe('devisApi - convertToReservation / getPdf', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('convertit en réservation', async () => {
    vi.mocked(api.post).mockResolvedValue({ reservation_id: 5 })

    const payload = { event_date: '2026-05-15', delivery_date: '2026-05-14', return_date: '2026-05-16', event_location: 'Paris' }
    const result = await devisApi.convertToReservation(1, payload)

    expect(api.post).toHaveBeenCalledWith('/devis/1/convert', payload)
    expect(result.reservation_id).toBe(5)
  })

  it('télécharge le PDF', async () => {
    const mockBlob = new Blob(['%PDF'], { type: 'application/pdf' })
    vi.mocked(fetchBlob).mockResolvedValue(mockBlob)

    const result = await devisApi.getPdf(1)

    expect(fetchBlob).toHaveBeenCalledWith('/devis/1/pdf')
    expect(result).toBeInstanceOf(Blob)
  })
})

describe('devisApi - modules / phases', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('ajoute un module à un devis', async () => {
    const mockModule = { id: 3, devis_id: 1, title: 'Sonorisation' }
    vi.mocked(api.post).mockResolvedValue(mockModule)

    await devisApi.addModule(1, { title: 'Sonorisation' } as Parameters<typeof devisApi.addModule>[1])

    expect(api.post).toHaveBeenCalledWith('/devis/1/modules', expect.any(Object))
  })

  it('met à jour un module', async () => {
    vi.mocked(api.patch).mockResolvedValue({ id: 3, title: 'Sonorisation pro' })

    await devisApi.updateModule(1, 3, { title: 'Sonorisation pro' })

    expect(api.patch).toHaveBeenCalledWith('/devis/1/modules/3', { title: 'Sonorisation pro' })
  })

  it('supprime un module', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await devisApi.deleteModule(1, 3)

    expect(api.delete).toHaveBeenCalledWith('/devis/1/modules/3')
  })

  it('ajoute une phase', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 7, devis_id: 1, name: 'Phase 1' })

    await devisApi.addPhase(1, { name: 'Phase 1' } as Parameters<typeof devisApi.addPhase>[1])

    expect(api.post).toHaveBeenCalledWith('/devis/1/phases', expect.any(Object))
  })

  it('supprime une phase', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await devisApi.deletePhase(1, 7)

    expect(api.delete).toHaveBeenCalledWith('/devis/1/phases/7')
  })
})
