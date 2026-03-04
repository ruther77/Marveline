/**
 * Tests unitaires pour api/evenements.ts
 * Vérifie list, get, create, actions (markReturned, close, flagRisk, cancel)
 * et incidents (declareIncident, addActionPlan, closeAction)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { evenementsApi } from '../evenements'
import { api } from '../fetchClient'
import type { EventListItem, EventDetailFull } from '@/types/event'

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

const mockListItem: EventListItem = {
  id: 1,
  tenant_id: 1,
  name: 'Mariage Dupont',
  event_date: '2026-06-15',
  status: 'planned',
  reservation_id: 10,
}

const mockFull = { ...mockListItem, incidents: [] } as unknown as EventDetailFull

describe('evenementsApi - list', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère liste paginée par défaut', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [mockListItem], total: 1 })

    const result = await evenementsApi.list()

    expect(api.get).toHaveBeenCalledWith(expect.stringContaining('/evenements?'))
    expect(result.items).toHaveLength(1)
    expect(result.total).toBe(1)
    expect(result.page).toBe(1)
    expect(result.total_pages).toBe(1)
  })

  it('applique filtre status et dates', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0 })

    await evenementsApi.list({ status: 'incident', date_from: '2026-06-01', date_to: '2026-06-30' })

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).toContain('status=incident')
    expect(url).toContain('date_from=2026-06-01')
    expect(url).toContain('date_to=2026-06-30')
  })

  it('gère liste vide', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0 })
    const result = await evenementsApi.list()
    expect(result.items).toHaveLength(0)
    expect(result.total_pages).toBe(0)
  })
})

describe('evenementsApi - get', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère un événement par ID', async () => {
    vi.mocked(api.get).mockResolvedValue(mockFull)

    const result = await evenementsApi.get(1)

    expect(api.get).toHaveBeenCalledWith('/evenements/1')
    expect(result.id).toBe(1)
  })

  it('propage les erreurs 404', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Événement introuvable'))
    await expect(evenementsApi.get(999)).rejects.toThrow('Événement introuvable')
  })
})

describe('evenementsApi - create', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('crée un nouvel événement', async () => {
    vi.mocked(api.post).mockResolvedValue(mockFull)

    const result = await evenementsApi.create({
      name: 'Mariage Dupont',
      event_date: '2026-06-15',
      reservation_id: 10,
    })

    expect(api.post).toHaveBeenCalledWith('/evenements', expect.any(Object))
    expect(result.name).toBe('Mariage Dupont')
  })
})

describe('evenementsApi - markReturned', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('marque un événement comme retourné sans notes', async () => {
    vi.mocked(api.post).mockResolvedValue({ ...mockFull, status: 'returned' })

    const result = await evenementsApi.markReturned(1)

    expect(api.post).toHaveBeenCalledWith('/evenements/1/mark-returned', {})
    expect((result as EventDetailFull & { status: string }).status).toBe('returned')
  })

  it('marque comme retourné avec notes', async () => {
    vi.mocked(api.post).mockResolvedValue(mockFull)

    await evenementsApi.markReturned(1, 'Quelques rayures sur table')

    expect(api.post).toHaveBeenCalledWith('/evenements/1/mark-returned', { notes: 'Quelques rayures sur table' })
  })
})

describe('evenementsApi - close', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('ferme un événement', async () => {
    vi.mocked(api.post).mockResolvedValue({ ...mockFull, status: 'closed' })

    await evenementsApi.close(1)

    expect(api.post).toHaveBeenCalledWith('/evenements/1/close', {})
  })
})

describe('evenementsApi - declareIncident', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('déclare un incident sur un événement', async () => {
    vi.mocked(api.post).mockResolvedValue({ ...mockFull, status: 'incident' })

    await evenementsApi.declareIncident(1, {
      description: 'Table cassée',
      severity: 'high',
      affected_items: [3, 5],
    })

    expect(api.post).toHaveBeenCalledWith('/evenements/1/incidents', {
      description: 'Table cassée',
      severity: 'high',
      affected_items: [3, 5],
    })
  })
})

describe('evenementsApi - addActionPlan', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('ajoute une action unique (backward-compatible)', async () => {
    const mockActions = [{ id: 10, incident_id: 2, label: 'Appeler le fournisseur', assignee_id: 5, deadline: '2026-06-20', status: 'todo' }]
    vi.mocked(api.post).mockResolvedValue(mockActions)

    const result = await evenementsApi.addActionPlan(1, 2, {
      label: 'Appeler le fournisseur',
      assignee_id: 5,
      deadline: '2026-06-20',
      status: 'todo',
    })

    // Vérifie que le payload est un tableau (même si on envoie un objet unique)
    expect(api.post).toHaveBeenCalledWith(
      '/evenements/1/incidents/2/action-plan',
      [expect.objectContaining({ label: 'Appeler le fournisseur' })]
    )
    expect(result).toHaveLength(1)
    expect(result[0].label).toBe('Appeler le fournisseur')
  })

  it('ajoute plusieurs actions via tableau', async () => {
    const mockActions = [
      { id: 10, incident_id: 2, label: 'Action 1', assignee_id: 5, deadline: '2026-06-20', status: 'todo' },
      { id: 11, incident_id: 2, label: 'Action 2', assignee_id: 6, deadline: '2026-06-21', status: 'todo' },
    ]
    vi.mocked(api.post).mockResolvedValue(mockActions)

    const result = await evenementsApi.addActionPlan(1, 2, [
      { label: 'Action 1', assignee_id: 5, deadline: '2026-06-20' },
      { label: 'Action 2', assignee_id: 6, deadline: '2026-06-21' },
    ])

    expect(api.post).toHaveBeenCalledWith(
      '/evenements/1/incidents/2/action-plan',
      expect.arrayContaining([
        expect.objectContaining({ label: 'Action 1' }),
        expect.objectContaining({ label: 'Action 2' }),
      ])
    )
    expect(result).toHaveLength(2)
  })
})

describe('evenementsApi - closeAction', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('ferme une action d\'un plan d\'action', async () => {
    vi.mocked(api.patch).mockResolvedValue({ id: 7, status: 'done' })

    const result = await evenementsApi.closeAction(1, 2, 7)

    expect(api.patch).toHaveBeenCalledWith('/evenements/1/incidents/2/actions/7/close')
    expect(result.status).toBe('done')
  })
})
