/**
 * Tests unitaires pour api/admin_settings.ts
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { adminSettingsApi, type TenantSettings } from '../admin_settings'
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

const mockSettings: TenantSettings = {
  company_name: 'Marveline Events',
  company_email: 'contact@marveline.fr',
  company_phone: '0123456789',
  company_address: '1 rue de la Paix, 75001 Paris',
  vat_rate: 20,
  hourly_rate_weekday: 5000,
  hourly_rate_weekend: 7500,
  deposit_rate: 40,
  default_currency: 'EUR',
}

describe('adminSettingsApi - get', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère les paramètres du tenant', async () => {
    vi.mocked(api.get).mockResolvedValue(mockSettings)

    const result = await adminSettingsApi.get()

    expect(api.get).toHaveBeenCalledWith('/admin/settings')
    expect(result.company_name).toBe('Marveline Events')
    expect(result.vat_rate).toBe(20)
    expect(result.deposit_rate).toBe(40)
  })

  it('propage les erreurs', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Unauthorized'))
    await expect(adminSettingsApi.get()).rejects.toThrow('Unauthorized')
  })
})

describe('adminSettingsApi - update', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('met à jour partiellement les paramètres', async () => {
    vi.mocked(api.patch).mockResolvedValue({ ...mockSettings, company_name: 'Marveline Pro' })

    const result = await adminSettingsApi.update({ company_name: 'Marveline Pro' })

    expect(api.patch).toHaveBeenCalledWith('/admin/settings', { company_name: 'Marveline Pro' })
    expect(result.company_name).toBe('Marveline Pro')
  })

  it('met à jour les taux financiers', async () => {
    vi.mocked(api.patch).mockResolvedValue({ ...mockSettings, vat_rate: 5.5, deposit_rate: 30 })

    const result = await adminSettingsApi.update({ vat_rate: 5.5, deposit_rate: 30 })

    expect(api.patch).toHaveBeenCalledWith('/admin/settings', { vat_rate: 5.5, deposit_rate: 30 })
    expect(result.deposit_rate).toBe(30)
  })
})
