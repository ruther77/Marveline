/**
 * Tests unitaires pour api/featureFlags.ts
 * Vérifie CRUD feature flags + toggle
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { featureFlagsApi } from '../featureFlags'
import apiClient from '../client'
import type { FeatureFlag, FeatureFlagList, FeatureFlagCreate, FeatureFlagUpdate } from '@/types/featureFlag'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('Feature Flags - list', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère liste paginée avec paramètres par défaut', async () => {
    const mockResponse = {
      items: [
        { id: 1, key: 'new_checkout', name: 'Nouveau Checkout', is_enabled: true },
        { id: 2, key: 'beta_features', name: 'Fonctionnalités Beta', is_enabled: false },
      ],
      total: 2,
      skip: 0,
      limit: 50,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await featureFlagsApi.list(1, 50)

    expect(apiClient.get).toHaveBeenCalledWith('/features', {
      params: { skip: 0, limit: 50 },
    })
    expect(result.items).toHaveLength(2)
    expect(result.total).toBe(2)
    expect(result.page).toBe(1)
    expect(result.per_page).toBe(50)
    expect(result.pages).toBe(1)
  })

  it('gère liste vide (0 feature flags)', async () => {
    const mockResponse = {
      items: [],
      total: 0,
      skip: 0,
      limit: 50,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await featureFlagsApi.list()

    expect(result.items).toEqual([])
    expect(result.total).toBe(0)
    expect(result.pages).toBe(0)
  })
})

describe('Feature Flags - get', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère un feature flag par ID', async () => {
    const mockFlag: FeatureFlag = {
      id: 1,
      key: 'new_checkout',
      name: 'Nouveau Checkout',
      description: 'Nouvelle interface de paiement',
      is_enabled: true,
      rollout_percentage: 50,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockFlag })

    const result = await featureFlagsApi.get(1)

    expect(apiClient.get).toHaveBeenCalledWith('/features/1')
    expect(result).toEqual(mockFlag)
    expect(result.key).toBe('new_checkout')
  })

  it('propage les erreurs 404 si feature flag non trouvé', async () => {
    const error = new Error('Feature flag not found')
    vi.mocked(apiClient.get).mockRejectedValue(error)

    await expect(featureFlagsApi.get(999)).rejects.toThrow('Feature flag not found')
  })
})

describe('Feature Flags - create', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('crée un nouveau feature flag', async () => {
    const newFlag: FeatureFlagCreate = {
      key: 'dark_mode',
      name: 'Mode Sombre',
      description: 'Activer le mode sombre',
      is_enabled: false,
      rollout_percentage: 0,
    }
    const mockResponse: FeatureFlag = {
      id: 5,
      key: 'dark_mode',
      name: 'Mode Sombre',
      description: 'Activer le mode sombre',
      is_enabled: false,
      rollout_percentage: 0,
      tenant_id: 1,
      created_at: '2026-02-16T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await featureFlagsApi.create(newFlag)

    expect(apiClient.post).toHaveBeenCalledWith('/features', newFlag)
    expect(result).toEqual(mockResponse)
    expect(result.id).toBe(5)
  })

  it('propage les erreurs 400 si clé déjà existante', async () => {
    const error = new Error('Feature flag key already exists')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    const newFlag: FeatureFlagCreate = {
      key: 'duplicate_key',
      name: 'Flag Duplicate',
    }

    await expect(featureFlagsApi.create(newFlag)).rejects.toThrow('Feature flag key already exists')
  })
})

describe('Feature Flags - update', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('met à jour un feature flag existant (PATCH partiel)', async () => {
    const updateData: FeatureFlagUpdate = {
      name: 'Nouveau Nom',
      rollout_percentage: 75,
    }
    const mockResponse: FeatureFlag = {
      id: 1,
      key: 'new_checkout',
      name: 'Nouveau Nom',
      description: 'Nouvelle interface de paiement',
      is_enabled: true,
      rollout_percentage: 75,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(apiClient.patch).mockResolvedValue({ data: mockResponse })

    const result = await featureFlagsApi.update(1, updateData)

    expect(apiClient.patch).toHaveBeenCalledWith('/features/1', updateData)
    expect(result.name).toBe('Nouveau Nom')
    expect(result.rollout_percentage).toBe(75)
  })

  it('propage les erreurs 404 si feature flag non trouvé', async () => {
    const error = new Error('Feature flag not found')
    vi.mocked(apiClient.patch).mockRejectedValue(error)

    await expect(featureFlagsApi.update(999, { name: 'Test' })).rejects.toThrow('Feature flag not found')
  })
})

describe('Feature Flags - delete', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('supprime un feature flag', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({})

    await featureFlagsApi.delete(1)

    expect(apiClient.delete).toHaveBeenCalledWith('/features/1')
  })

  it('propage les erreurs 404 si feature flag non trouvé', async () => {
    const error = new Error('Feature flag not found')
    vi.mocked(apiClient.delete).mockRejectedValue(error)

    await expect(featureFlagsApi.delete(999)).rejects.toThrow('Feature flag not found')
  })
})

describe('Feature Flags - toggle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('active un feature flag (is_enabled=true)', async () => {
    const mockResponse: FeatureFlag = {
      id: 1,
      key: 'new_checkout',
      name: 'Nouveau Checkout',
      description: 'Nouvelle interface',
      is_enabled: true,
      rollout_percentage: 100,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(apiClient.patch).mockResolvedValue({ data: mockResponse })

    const result = await featureFlagsApi.toggle(1, true)

    expect(apiClient.patch).toHaveBeenCalledWith('/features/1', { is_enabled: true })
    expect(result.is_enabled).toBe(true)
  })

  it('désactive un feature flag (is_enabled=false)', async () => {
    const mockResponse: FeatureFlag = {
      id: 1,
      key: 'new_checkout',
      name: 'Nouveau Checkout',
      description: 'Nouvelle interface',
      is_enabled: false,
      rollout_percentage: 0,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(apiClient.patch).mockResolvedValue({ data: mockResponse })

    const result = await featureFlagsApi.toggle(1, false)

    expect(apiClient.patch).toHaveBeenCalledWith('/features/1', { is_enabled: false })
    expect(result.is_enabled).toBe(false)
  })
})
