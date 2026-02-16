/**
 * Tests unitaires pour api/apiKeys.ts
 * Vérifie CRUD API keys + rotation secrets
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiKeysApi } from '../apiKeys'
import apiClient from '../client'
import type { ApiKey, ApiKeyList, ApiKeyCreated, ApiKeyCreate, ApiKeyUpdate } from '@/types/apiKey'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('API Keys - list', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère liste paginée avec paramètres par défaut', async () => {
    const mockResponse = {
      items: [
        { id: 1, name: 'Production Key', key_preview: 'pk_live_****1234', is_active: true },
        { id: 2, name: 'Dev Key', key_preview: 'pk_test_****5678', is_active: true },
      ],
      total: 2,
      skip: 0,
      limit: 50,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await apiKeysApi.list(1, 50, false)

    expect(apiClient.get).toHaveBeenCalledWith('/api-keys', {
      params: { skip: 0, limit: 50, include_inactive: false },
    })
    expect(result.items).toHaveLength(2)
    expect(result.total).toBe(2)
    expect(result.page).toBe(1)
    expect(result.per_page).toBe(50)
    expect(result.pages).toBe(1)
  })

  it('inclut les API keys inactives si include_inactive=true', async () => {
    const mockResponse = {
      items: [
        { id: 1, name: 'Active Key', is_active: true },
        { id: 2, name: 'Inactive Key', is_active: false },
      ],
      total: 2,
      skip: 0,
      limit: 50,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    await apiKeysApi.list(1, 50, true)

    expect(apiClient.get).toHaveBeenCalledWith('/api-keys', {
      params: { skip: 0, limit: 50, include_inactive: true },
    })
  })

  it('gère liste vide (0 API keys)', async () => {
    const mockResponse = {
      items: [],
      total: 0,
      skip: 0,
      limit: 50,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await apiKeysApi.list()

    expect(result.items).toEqual([])
    expect(result.total).toBe(0)
    expect(result.pages).toBe(0)
  })
})

describe('API Keys - get', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère une API key par ID', async () => {
    const mockApiKey: ApiKey = {
      id: 1,
      name: 'Production Key',
      key_preview: 'pk_live_****1234',
      description: 'Production environment key',
      scopes: ['read:products', 'write:orders'],
      is_active: true,
      last_used_at: '2026-02-15T10:30:00Z',
      created_at: '2026-01-01T00:00:00Z',
      expires_at: null,
      tenant_id: 1,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockApiKey })

    const result = await apiKeysApi.get(1)

    expect(apiClient.get).toHaveBeenCalledWith('/api-keys/1')
    expect(result).toEqual(mockApiKey)
    expect(result.name).toBe('Production Key')
  })

  it('propage les erreurs 404 si API key non trouvée', async () => {
    const error = new Error('API key not found')
    vi.mocked(apiClient.get).mockRejectedValue(error)

    await expect(apiKeysApi.get(999)).rejects.toThrow('API key not found')
  })
})

describe('API Keys - create', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('crée une nouvelle API key et retourne le secret', async () => {
    const newKey: ApiKeyCreate = {
      name: 'New API Key',
      description: 'Key for testing',
      scopes: ['read:products'],
      expires_at: null,
    }
    const mockResponse: ApiKeyCreated = {
      id: 5,
      name: 'New API Key',
      key_preview: 'pk_test_****abcd',
      description: 'Key for testing',
      scopes: ['read:products'],
      is_active: true,
      created_at: '2026-02-16T00:00:00Z',
      expires_at: null,
      tenant_id: 1,
      api_key: 'pk_test_1234567890abcdef1234567890abcdef',
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await apiKeysApi.create(newKey)

    expect(apiClient.post).toHaveBeenCalledWith('/api-keys', newKey)
    expect(result).toEqual(mockResponse)
    expect(result.api_key).toBeDefined()
    expect(result.api_key?.startsWith('pk_test_')).toBe(true)
  })

  it('propage les erreurs 400 si données invalides', async () => {
    const error = new Error('Invalid scopes')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    const newKey: ApiKeyCreate = {
      name: 'Invalid Key',
      scopes: ['invalid:scope'],
    }

    await expect(apiKeysApi.create(newKey)).rejects.toThrow('Invalid scopes')
  })
})

describe('API Keys - update', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('met à jour une API key existante (PATCH partiel)', async () => {
    const updateData: ApiKeyUpdate = {
      name: 'Updated Key Name',
      is_active: false,
    }
    const mockResponse: ApiKey = {
      id: 1,
      name: 'Updated Key Name',
      key_preview: 'pk_live_****1234',
      description: 'Production environment key',
      scopes: ['read:products', 'write:orders'],
      is_active: false,
      last_used_at: '2026-02-15T10:30:00Z',
      created_at: '2026-01-01T00:00:00Z',
      expires_at: null,
      tenant_id: 1,
    }
    vi.mocked(apiClient.patch).mockResolvedValue({ data: mockResponse })

    const result = await apiKeysApi.update(1, updateData)

    expect(apiClient.patch).toHaveBeenCalledWith('/api-keys/1', updateData)
    expect(result.name).toBe('Updated Key Name')
    expect(result.is_active).toBe(false)
  })

  it('propage les erreurs 404 si API key non trouvée', async () => {
    const error = new Error('API key not found')
    vi.mocked(apiClient.patch).mockRejectedValue(error)

    await expect(apiKeysApi.update(999, { name: 'Test' })).rejects.toThrow('API key not found')
  })
})

describe('API Keys - delete', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('supprime une API key et retourne les détails', async () => {
    const mockResponse: ApiKey = {
      id: 1,
      name: 'Deleted Key',
      key_preview: 'pk_live_****1234',
      description: 'Key to delete',
      scopes: ['read:products'],
      is_active: false,
      last_used_at: null,
      created_at: '2026-01-01T00:00:00Z',
      expires_at: null,
      tenant_id: 1,
    }
    vi.mocked(apiClient.delete).mockResolvedValue({ data: mockResponse })

    const result = await apiKeysApi.delete(1)

    expect(apiClient.delete).toHaveBeenCalledWith('/api-keys/1')
    expect(result).toEqual(mockResponse)
  })

  it('propage les erreurs 404 si API key non trouvée', async () => {
    const error = new Error('API key not found')
    vi.mocked(apiClient.delete).mockRejectedValue(error)

    await expect(apiKeysApi.delete(999)).rejects.toThrow('API key not found')
  })
})

describe('API Keys - rotate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('effectue rotation du secret et retourne nouveau secret', async () => {
    const mockResponse: ApiKeyCreated = {
      id: 1,
      name: 'Production Key',
      key_preview: 'pk_live_****9876',
      description: 'Production environment key',
      scopes: ['read:products', 'write:orders'],
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      expires_at: null,
      tenant_id: 1,
      api_key: 'pk_live_new1234567890abcdef1234567890abcdef',
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await apiKeysApi.rotate(1)

    expect(apiClient.post).toHaveBeenCalledWith('/api-keys/1/rotate')
    expect(result.api_key).toBeDefined()
    expect(result.api_key?.startsWith('pk_live_')).toBe(true)
    expect(result.key_preview).toBe('pk_live_****9876')
  })

  it('propage les erreurs 404 si API key non trouvée', async () => {
    const error = new Error('API key not found')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    await expect(apiKeysApi.rotate(999)).rejects.toThrow('API key not found')
  })
})
