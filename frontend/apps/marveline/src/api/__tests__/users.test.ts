/**
 * Tests unitaires pour api/users.ts
 * Vérifie la couche self-service profile (/users/me)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { usersApi } from '../users'
import { api } from '../fetchClient'
import type { User } from '@/types'

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

describe('Users API (self-service)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getMyProfile appelle GET /users/me', async () => {
    const mockUser: User = {
      id: 7,
      email: 'profil@test.com',
      full_name: 'Jean Dupont',
      role: 'manager',
      tenant_id: 3,
      is_active: true,
      permissions: ['users:read'],
      created_at: '2026-03-05T11:00:00Z',
      first_name: 'Jean',
      last_name: 'Dupont',
      updated_at: '2026-03-05T11:00:00Z',
    }
    vi.mocked(api.get).mockResolvedValue(mockUser)

    const result = await usersApi.getMyProfile()

    expect(api.get).toHaveBeenCalledWith('/users/me')
    expect(result).toEqual(mockUser)
  })

  it('updateMyProfile appelle PATCH /users/me avec payload', async () => {
    const payload = {
      first_name: 'Jeanne',
      last_name: 'Durand',
      email: 'jeanne@test.com',
    }
    const mockUpdated: User = {
      id: 7,
      email: 'jeanne@test.com',
      full_name: 'Jeanne Durand',
      role: 'manager',
      tenant_id: 3,
      is_active: true,
      permissions: ['users:read'],
      created_at: '2026-03-05T11:00:00Z',
      first_name: 'Jeanne',
      last_name: 'Durand',
      updated_at: '2026-03-05T11:10:00Z',
    }
    vi.mocked(api.patch).mockResolvedValue(mockUpdated)

    const result = await usersApi.updateMyProfile(payload)

    expect(api.patch).toHaveBeenCalledWith('/users/me', payload)
    expect(result).toEqual(mockUpdated)
  })
})
