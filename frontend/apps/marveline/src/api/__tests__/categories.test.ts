/**
 * Tests unitaires pour api/categories.ts
 * Vérifie CRUD categories + tree + filtres
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { categoriesApi } from '../categories'
import { api } from '../fetchClient'
import type { Category, CategoryTreeNode, CategoryCreate, CategoryUpdate } from '@/types/product'

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

describe('API Categories - getCategories', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère liste de catégories actives par défaut (active_only=true)', async () => {
    const mockResponse = {
      items: [
        { id: 1, name: 'Assiettes', slug: 'assiettes', is_active: true },
        { id: 2, name: 'Verres', slug: 'verres', is_active: true },
      ],
      total: 2,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await categoriesApi.getCategories(true)

    expect(api.get).toHaveBeenCalledWith('/categories?active_only=true&limit=1000')
    expect(result).toHaveLength(2)
    expect(result[0].slug).toBe('assiettes')
  })

  it('récupère toutes les catégories si active_only=false', async () => {
    const mockResponse = {
      items: [
        { id: 1, name: 'Catégorie Active', is_active: true },
        { id: 2, name: 'Catégorie Inactive', is_active: false },
      ],
      total: 2,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await categoriesApi.getCategories(false)

    expect(api.get).toHaveBeenCalledWith('/categories?active_only=false&limit=1000')
    expect(result).toHaveLength(2)
  })

  it('gère liste vide (0 catégories)', async () => {
    const mockResponse = {
      items: [],
      total: 0,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await categoriesApi.getCategories()

    expect(result).toEqual([])
  })
})

describe('API Categories - getCategoryTree', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère arbre hiérarchique avec enfants', async () => {
    const mockTree: CategoryTreeNode[] = [
      {
        id: 1,
        name: 'Vaisselle',
        slug: 'vaisselle',
        parent_id: null,
        is_active: true,
        children: [
          {
            id: 2,
            name: 'Assiettes',
            slug: 'assiettes',
            parent_id: 1,
            is_active: true,
            children: [],
          },
        ],
      },
    ]
    vi.mocked(api.get).mockResolvedValue(mockTree)

    const result = await categoriesApi.getCategoryTree()

    expect(api.get).toHaveBeenCalledWith('/categories/tree')
    expect(result).toHaveLength(1)
    expect(result[0].children).toHaveLength(1)
    expect(result[0].children![0].name).toBe('Assiettes')
  })

  it('gère arbre vide (aucune catégorie)', async () => {
    vi.mocked(api.get).mockResolvedValue([])

    const result = await categoriesApi.getCategoryTree()

    expect(result).toEqual([])
  })
})

describe('API Categories - getCategory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère une catégorie par ID', async () => {
    const mockCategory: Category = {
      id: 1,
      name: 'Assiettes',
      slug: 'assiettes',
      description: 'Description assiettes',
      parent_id: null,
      icon: 'plate',
      color: '#FF5733',
      sort_order: 1,
      is_active: true,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }
    vi.mocked(api.get).mockResolvedValue(mockCategory)

    const result = await categoriesApi.getCategory(1)

    expect(api.get).toHaveBeenCalledWith('/categories/1')
    expect(result).toEqual(mockCategory)
    expect(result.slug).toBe('assiettes')
  })

  it('propage les erreurs 404 si catégorie non trouvée', async () => {
    const error = new Error('Category not found')
    vi.mocked(api.get).mockRejectedValue(error)

    await expect(categoriesApi.getCategory(999)).rejects.toThrow('Category not found')
  })
})

describe('API Categories - createCategory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('crée une nouvelle catégorie', async () => {
    const newCategory: CategoryCreate = {
      name: 'Nouvelle Catégorie',
      description: 'Description nouvelle',
      parent_id: null,
      icon: 'icon',
      color: '#000000',
      sort_order: 10,
    }
    const mockResponse: Category = {
      id: 5,
      name: 'Nouvelle Catégorie',
      slug: 'nouvelle-categorie',
      description: 'Description nouvelle',
      parent_id: null,
      icon: 'icon',
      color: '#000000',
      sort_order: 10,
      is_active: true,
      tenant_id: 1,
      created_at: '2026-02-16T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    const result = await categoriesApi.createCategory(newCategory)

    expect(api.post).toHaveBeenCalledWith('/categories', newCategory)
    expect(result).toEqual(mockResponse)
    expect(result.id).toBe(5)
  })

  it('propage les erreurs 403 si non autorisé', async () => {
    const error = new Error('Forbidden')
    vi.mocked(api.post).mockRejectedValue(error)

    const newCategory: CategoryCreate = {
      name: 'Catégorie Test',
    }

    await expect(categoriesApi.createCategory(newCategory)).rejects.toThrow('Forbidden')
  })
})

describe('API Categories - updateCategory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('met à jour une catégorie existante (PATCH partiel)', async () => {
    const updateData: CategoryUpdate = {
      name: 'Catégorie Modifiée',
      color: '#FF0000',
    }
    const mockResponse: Category = {
      id: 1,
      name: 'Catégorie Modifiée',
      slug: 'categorie-modifiee',
      description: 'Description originale',
      parent_id: null,
      icon: 'icon',
      color: '#FF0000',
      sort_order: 1,
      is_active: true,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(api.patch).mockResolvedValue(mockResponse)

    const result = await categoriesApi.updateCategory(1, updateData)

    expect(api.patch).toHaveBeenCalledWith('/categories/1', updateData)
    expect(result.name).toBe('Catégorie Modifiée')
    expect(result.color).toBe('#FF0000')
  })

  it('propage les erreurs 404 si catégorie non trouvée', async () => {
    const error = new Error('Category not found')
    vi.mocked(api.patch).mockRejectedValue(error)

    await expect(categoriesApi.updateCategory(999, { name: 'Test' })).rejects.toThrow('Category not found')
  })
})

describe('API Categories - deleteCategory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('supprime une catégorie (soft delete)', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await categoriesApi.deleteCategory(1)

    expect(api.delete).toHaveBeenCalledWith('/categories/1')
  })

  it('propage les erreurs 404 si catégorie non trouvée', async () => {
    const error = new Error('Category not found')
    vi.mocked(api.delete).mockRejectedValue(error)

    await expect(categoriesApi.deleteCategory(999)).rejects.toThrow('Category not found')
  })
})
