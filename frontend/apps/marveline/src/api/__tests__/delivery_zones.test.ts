/**
 * Tests unitaires pour api/delivery_zones.ts
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { deliveryZonesApi } from '../delivery_zones'
import { api } from '../fetchClient'
import type { DeliveryZone } from '@/types/delivery_zone'

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

const mockZone: DeliveryZone = {
  id: 1,
  name: 'Paris intramuros',
  price_cents: 2500,
  is_active: true,
} as unknown as DeliveryZone

describe('deliveryZonesApi - getZones', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('retourne un tableau direct', async () => {
    vi.mocked(api.get).mockResolvedValue([mockZone])

    const result = await deliveryZonesApi.getZones()

    expect(api.get).toHaveBeenCalledWith('/delivery-zones')
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('Paris intramuros')
  })

  it('retourne items si réponse enveloppée', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [mockZone] })

    const result = await deliveryZonesApi.getZones()
    expect(result).toHaveLength(1)
  })

  it('gère liste vide', async () => {
    vi.mocked(api.get).mockResolvedValue([])
    const result = await deliveryZonesApi.getZones()
    expect(result).toHaveLength(0)
  })
})

describe('deliveryZonesApi - getZone', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère une zone par ID', async () => {
    vi.mocked(api.get).mockResolvedValue(mockZone)

    const result = await deliveryZonesApi.getZone(1)

    expect(api.get).toHaveBeenCalledWith('/delivery-zones/1')
    expect(result.id).toBe(1)
  })
})

describe('deliveryZonesApi - createZone', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('crée une zone de livraison', async () => {
    vi.mocked(api.post).mockResolvedValue(mockZone)

    const result = await deliveryZonesApi.createZone({ name: 'Paris intramuros', price_cents: 2500 } as Parameters<typeof deliveryZonesApi.createZone>[0])

    expect(api.post).toHaveBeenCalledWith('/delivery-zones', expect.any(Object))
    expect(result.price_cents).toBe(2500)
  })
})

describe('deliveryZonesApi - updateZone', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('met à jour une zone', async () => {
    vi.mocked(api.patch).mockResolvedValue({ ...mockZone, price_cents: 3000 })

    const result = await deliveryZonesApi.updateZone(1, { price_cents: 3000 })

    expect(api.patch).toHaveBeenCalledWith('/delivery-zones/1', { price_cents: 3000 })
    expect(result.price_cents).toBe(3000)
  })
})

describe('deliveryZonesApi - deleteZone', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('supprime une zone', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await deliveryZonesApi.deleteZone(1)

    expect(api.delete).toHaveBeenCalledWith('/delivery-zones/1')
  })
})
