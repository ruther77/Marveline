/**
 * Tests unitaires pour api/planning.ts
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { planningApi } from '../planning'
import { api } from '../fetchClient'
import type { PlanningDayResponse, PlanningWeek, PlanningMonth, PlanningResources } from '@/types/planning'

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

const mockDay = { date: '2026-03-01', reservations: [], events: [] } as unknown as PlanningDayResponse
const mockWeek = { week_start: '2026-03-01', days: [] } as unknown as PlanningWeek
const mockMonth = { year: 2026, month: 3, days: [] } as unknown as PlanningMonth
const mockResources = { date: '2026-03-01', products: [] } as unknown as PlanningResources

describe('planningApi - day', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère le planning du jour sans date', async () => {
    vi.mocked(api.get).mockResolvedValue(mockDay)

    await planningApi.day()

    expect(api.get).toHaveBeenCalledWith('/planning/day')
  })

  it('récupère le planning d\'une date spécifique', async () => {
    vi.mocked(api.get).mockResolvedValue(mockDay)

    await planningApi.day('2026-03-15')

    expect(api.get).toHaveBeenCalledWith('/planning/day?date=2026-03-15')
  })
})

describe('planningApi - week', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère la semaine sans date', async () => {
    vi.mocked(api.get).mockResolvedValue(mockWeek)

    await planningApi.week()

    expect(api.get).toHaveBeenCalledWith('/planning/week')
  })

  it('récupère la semaine d\'une date', async () => {
    vi.mocked(api.get).mockResolvedValue(mockWeek)

    await planningApi.week('2026-03-01')

    expect(api.get).toHaveBeenCalledWith('/planning/week?date=2026-03-01')
  })
})

describe('planningApi - month', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère le mois sans date', async () => {
    vi.mocked(api.get).mockResolvedValue(mockMonth)

    await planningApi.month()

    expect(api.get).toHaveBeenCalledWith('/planning/month')
  })

  it('récupère un mois spécifique', async () => {
    vi.mocked(api.get).mockResolvedValue(mockMonth)

    await planningApi.month('2026-03-01')

    expect(api.get).toHaveBeenCalledWith('/planning/month?date=2026-03-01')
  })
})

describe('planningApi - resources', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère les ressources sans date', async () => {
    vi.mocked(api.get).mockResolvedValue(mockResources)

    await planningApi.resources()

    expect(api.get).toHaveBeenCalledWith('/planning/resources')
  })

  it('récupère les ressources d\'une date', async () => {
    vi.mocked(api.get).mockResolvedValue(mockResources)

    await planningApi.resources('2026-03-15')

    expect(api.get).toHaveBeenCalledWith('/planning/resources?date=2026-03-15')
  })
})
