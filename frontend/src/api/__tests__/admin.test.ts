/**
 * Tests unitaires pour api/admin.ts
 * Vérifie CRUD users + sessions + audit logs
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { adminApi } from '../admin'
import apiClient from '../client'
import type { User, UserCreate, UserUpdate, Session, AuditLog } from '@/types'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('Admin API - Users CRUD', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère liste paginée d\'utilisateurs', async () => {
    const mockResponse = {
      items: [
        { id: 1, email: 'admin@test.com', role: 'admin', is_active: true },
        { id: 2, email: 'user@test.com', role: 'user', is_active: true },
      ],
      total: 2,
      skip: 0,
      limit: 20,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await adminApi.getUsers(1, 20)

    expect(apiClient.get).toHaveBeenCalledWith('/users', {
      params: { skip: 0, limit: 20 },
    })
    expect(result.items).toHaveLength(2)
    expect(result.total).toBe(2)
    expect(result.page).toBe(1)
    expect(result.pages).toBe(1)
  })

  it('gère liste vide (0 utilisateurs)', async () => {
    const mockResponse = {
      items: [],
      total: 0,
      skip: 0,
      limit: 20,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await adminApi.getUsers()

    expect(result.items).toEqual([])
    expect(result.total).toBe(0)
    expect(result.pages).toBe(0)
  })

  it('récupère un utilisateur par ID', async () => {
    const mockUser: User = {
      id: 1,
      email: 'admin@test.com',
      tenant_id: 1,
      role: 'admin',
      is_active: true,
      mfa_enabled: false,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockUser })

    const result = await adminApi.getUser(1)

    expect(apiClient.get).toHaveBeenCalledWith('/users/1')
    expect(result).toEqual(mockUser)
    expect(result.email).toBe('admin@test.com')
  })

  it('propage les erreurs 404 si utilisateur non trouvé (getUser)', async () => {
    const error = new Error('User not found')
    vi.mocked(apiClient.get).mockRejectedValue(error)

    await expect(adminApi.getUser(999)).rejects.toThrow('User not found')
  })

  it('crée un nouvel utilisateur', async () => {
    const newUser: UserCreate = {
      email: 'newuser@test.com',
      password: 'SecurePass123!',
      role: 'user',
    }
    const mockResponse: User = {
      id: 5,
      email: 'newuser@test.com',
      tenant_id: 1,
      role: 'user',
      is_active: true,
      mfa_enabled: false,
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await adminApi.createUser(newUser)

    expect(apiClient.post).toHaveBeenCalledWith('/users', newUser)
    expect(result).toEqual(mockResponse)
    expect(result.id).toBe(5)
  })

  it('propage les erreurs 400 si email déjà existant (createUser)', async () => {
    const error = new Error('Email already exists')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    const newUser: UserCreate = {
      email: 'duplicate@test.com',
      password: 'password',
      role: 'user',
    }

    await expect(adminApi.createUser(newUser)).rejects.toThrow('Email already exists')
  })

  it('met à jour un utilisateur existant (PATCH partiel)', async () => {
    const updateData: UserUpdate = {
      role: 'admin',
      is_active: true,
    }
    const mockResponse: User = {
      id: 1,
      email: 'user@test.com',
      tenant_id: 1,
      role: 'admin',
      is_active: true,
      mfa_enabled: false,
    }
    vi.mocked(apiClient.patch).mockResolvedValue({ data: mockResponse })

    const result = await adminApi.updateUser(1, updateData)

    expect(apiClient.patch).toHaveBeenCalledWith('/users/1', updateData)
    expect(result.role).toBe('admin')
  })

  it('propage les erreurs 404 si utilisateur non trouvé (updateUser)', async () => {
    const error = new Error('User not found')
    vi.mocked(apiClient.patch).mockRejectedValue(error)

    await expect(adminApi.updateUser(999, { role: 'admin' })).rejects.toThrow('User not found')
  })

  it('supprime un utilisateur', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({})

    await adminApi.deleteUser(1)

    expect(apiClient.delete).toHaveBeenCalledWith('/users/1')
  })

  it('propage les erreurs 404 si utilisateur non trouvé (deleteUser)', async () => {
    const error = new Error('User not found')
    vi.mocked(apiClient.delete).mockRejectedValue(error)

    await expect(adminApi.deleteUser(999)).rejects.toThrow('User not found')
  })
})

describe('Admin API - Sessions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère toutes les sessions avec compteurs', async () => {
    const mockResponse = {
      sessions: [
        { id: 'session-1', user_id: 1, ip_address: '192.168.1.1', is_active: true },
        { id: 'session-2', user_id: 2, ip_address: '192.168.1.2', is_active: true },
      ],
      total: 2,
      active_count: 2,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await adminApi.getSessions()

    expect(apiClient.get).toHaveBeenCalledWith('/sessions')
    expect(result.sessions).toHaveLength(2)
    expect(result.total).toBe(2)
    expect(result.active_count).toBe(2)
  })

  it('récupère sessions de l\'utilisateur courant', async () => {
    const mockResponse = {
      sessions: [
        { id: 'session-1', user_id: 1, ip_address: '192.168.1.1', is_active: true },
      ],
      total: 1,
      active_count: 1,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await adminApi.getUserSessions()

    expect(apiClient.get).toHaveBeenCalledWith('/sessions')
    expect(result).toHaveLength(1)
  })

  it('termine une session spécifique', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({})

    await adminApi.terminateSession('session-123')

    expect(apiClient.delete).toHaveBeenCalledWith('/sessions/session-123')
  })

  it('termine toutes les sessions', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({})

    await adminApi.terminateAllSessions()

    expect(apiClient.delete).toHaveBeenCalledWith('/sessions')
  })
})

describe('Admin API - Audit Logs', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère audit logs avec pagination', async () => {
    const mockResponse = {
      logs: [
        { id: 1, user_id: 1, action: 'user.login', timestamp: '2026-02-16T10:00:00Z' },
        { id: 2, user_id: 2, action: 'product.create', timestamp: '2026-02-16T11:00:00Z' },
      ],
      total: 2,
      skip: 0,
      limit: 50,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await adminApi.getAuditLogs(1, 50)

    expect(apiClient.get).toHaveBeenCalledWith('/audit', {
      params: { skip: 0, limit: 50 },
    })
    expect(result.items).toHaveLength(2)
    expect(result.total).toBe(2)
  })

  it('applique filtres sur audit logs (user_id, action, dates)', async () => {
    const mockResponse = {
      logs: [
        { id: 1, user_id: 1, action: 'user.login', timestamp: '2026-02-16T10:00:00Z' },
      ],
      total: 1,
      skip: 0,
      limit: 50,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    await adminApi.getAuditLogs(1, 50, {
      user_id: 1,
      action: 'user.login',
      from_date: '2026-02-01',
      to_date: '2026-02-28',
    })

    expect(apiClient.get).toHaveBeenCalledWith('/audit', {
      params: {
        skip: 0,
        limit: 50,
        user_id: 1,
        action: 'user.login',
        start_date: '2026-02-01',
        end_date: '2026-02-28',
      },
    })
  })
})
