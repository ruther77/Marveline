/**
 * Tests unitaires pour api/suppliers.ts
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { suppliersApi } from '../suppliers'
import { api } from '../fetchClient'
import type { Supplier } from '@/types/supplier'

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

const mockSupplier: Supplier = {
  id: 1,
  name: 'Fournisseur Leclerc',
  email: 'contact@leclerc.fr',
  phone: '0612345678',
  is_active: true,
} as unknown as Supplier

describe('suppliersApi - list', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère la liste des fournisseurs', async () => {
    vi.mocked(api.get).mockResolvedValue([mockSupplier])

    const result = await suppliersApi.list()

    expect(api.get).toHaveBeenCalledWith('/suppliers')
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('Fournisseur Leclerc')
  })

  it('gère liste vide', async () => {
    vi.mocked(api.get).mockResolvedValue([])
    const result = await suppliersApi.list()
    expect(result).toHaveLength(0)
  })
})

describe('suppliersApi - get', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère un fournisseur par ID', async () => {
    vi.mocked(api.get).mockResolvedValue(mockSupplier)

    const result = await suppliersApi.get(1)

    expect(api.get).toHaveBeenCalledWith('/suppliers/1')
    expect(result.id).toBe(1)
  })

  it('propage les erreurs 404', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Fournisseur introuvable'))
    await expect(suppliersApi.get(999)).rejects.toThrow('Fournisseur introuvable')
  })
})

describe('suppliersApi - create', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('crée un fournisseur', async () => {
    vi.mocked(api.post).mockResolvedValue(mockSupplier)

    const result = await suppliersApi.create({ name: 'Fournisseur Leclerc', email: 'contact@leclerc.fr' } as Parameters<typeof suppliersApi.create>[0])

    expect(api.post).toHaveBeenCalledWith('/suppliers', expect.any(Object))
    expect(result.name).toBe('Fournisseur Leclerc')
  })
})

describe('suppliersApi - update', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('met à jour un fournisseur', async () => {
    vi.mocked(api.patch).mockResolvedValue({ ...mockSupplier, phone: '0699999999' })

    const result = await suppliersApi.update(1, { phone: '0699999999' })

    expect(api.patch).toHaveBeenCalledWith('/suppliers/1', { phone: '0699999999' })
    expect(result.phone).toBe('0699999999')
  })
})

describe('suppliersApi - delete', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('supprime un fournisseur', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await suppliersApi.delete(1)

    expect(api.delete).toHaveBeenCalledWith('/suppliers/1')
  })
})
