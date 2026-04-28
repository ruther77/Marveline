/**
 * Tests unitaires pour api/notifications.ts
 * Vérifie list (avec filtres), markRead, markAllRead
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { notificationsApi } from '../notifications'
import { api } from '../fetchClient'
import type { Notification, NotificationList } from '@/types/notification'

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

const mockNotif: Notification = {
  id: 1,
  tenant_id: 1,
  user_id: 5,
  type: 'reservation_confirmed',
  title: 'Réservation confirmée',
  message: 'RES-0042 a été confirmée',
  link: '/reservations/1',
  is_read: false,
  created_at: '2026-02-20T10:00:00',
  read_at: null,
}

const mockList: NotificationList = {
  items: [mockNotif],
  total: 1,
  unread_count: 1,
}

describe('notificationsApi - list', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère la liste sans paramètres', async () => {
    vi.mocked(api.get).mockResolvedValue(mockList)

    const result = await notificationsApi.list()

    expect(api.get).toHaveBeenCalledWith('/notifications')
    expect(result.items).toHaveLength(1)
    expect(result.unread_count).toBe(1)
  })

  it('filtre les non-lues seulement', async () => {
    vi.mocked(api.get).mockResolvedValue(mockList)

    await notificationsApi.list({ unread_only: true })

    expect(api.get).toHaveBeenCalledWith('/notifications?unread_only=true')
  })

  it('applique pagination (skip + limit)', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, unread_count: 0 })

    await notificationsApi.list({ skip: 20, limit: 10 })

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).toContain('skip=20')
    expect(url).toContain('limit=10')
  })

  it('gère liste vide', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, unread_count: 0 })

    const result = await notificationsApi.list()
    expect(result.items).toHaveLength(0)
    expect(result.unread_count).toBe(0)
  })
})

describe('notificationsApi - markRead', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('marque une notification comme lue', async () => {
    const readNotif = { ...mockNotif, is_read: true, read_at: '2026-02-20T12:00:00' }
    vi.mocked(api.post).mockResolvedValue(readNotif)

    const result = await notificationsApi.markRead(1)

    expect(api.post).toHaveBeenCalledWith('/notifications/1/read', {})
    expect(result.is_read).toBe(true)
    expect(result.read_at).toBeTruthy()
  })

  it('propage les erreurs 404', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('Notification introuvable'))
    await expect(notificationsApi.markRead(999)).rejects.toThrow('Notification introuvable')
  })
})

describe('notificationsApi - markAllRead', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('marque toutes les notifications comme lues', async () => {
    vi.mocked(api.post).mockResolvedValue({ marked_read: 5 })

    const result = await notificationsApi.markAllRead()

    expect(api.post).toHaveBeenCalledWith('/notifications/read-all', {})
    expect(result.marked_read).toBe(5)
  })

  it('retourne 0 si aucune notification à marquer', async () => {
    vi.mocked(api.post).mockResolvedValue({ marked_read: 0 })

    const result = await notificationsApi.markAllRead()
    expect(result.marked_read).toBe(0)
  })
})
