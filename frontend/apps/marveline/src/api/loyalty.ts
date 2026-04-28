import { api } from './fetchClient'
import type {
  LoyaltyMemberCreate,
  LoyaltyMemberProfile,
  LoyaltyMemberResponse,
  PaginatedLoyaltyMembers,
  CreditRequest,
  CreditResponse,
  RevenueCreditRequest,
  RedeemRequest,
  RewardRedemptionResponse,
  RewardsCatalogCreate,
  RewardsCatalogUpdate,
  RewardsCatalogResponse,
  FlashOfferCreate,
  FlashOfferResponse,
  AdjustPointsRequest,
  LoyaltyDashboardMetrics,
  JoinResponse,
  ScanRequest,
  LoyaltyTier,
} from '../types/loyalty'

export const loyaltyApi = {
  // ── Public ───────────────────────────────────────────────────────────────
  join: async (data: LoyaltyMemberCreate): Promise<JoinResponse> => {
    return api.post<JoinResponse>('/loyalty/join', data)
  },

  // ── Staff (scan, credit, redeem) ─────────────────────────────────────────
  scan: async (data: ScanRequest): Promise<LoyaltyMemberProfile> => {
    return api.post<LoyaltyMemberProfile>('/loyalty/scan', data)
  },

  creditPoints: async (data: CreditRequest): Promise<CreditResponse> => {
    return api.post<CreditResponse>('/loyalty/credit', data)
  },

  creditRevenue: async (data: RevenueCreditRequest): Promise<{ status: string }> => {
    return api.post<{ status: string }>('/loyalty/credit-revenue', data)
  },

  redeem: async (data: RedeemRequest): Promise<RewardRedemptionResponse> => {
    return api.post<RewardRedemptionResponse>('/loyalty/redeem', data)
  },

  cancelTransaction: async (orderId: number): Promise<{ status: string }> => {
    return api.post<{ status: string }>(`/loyalty/cancel-transaction?order_id=${orderId}`)
  },

  // ── Client ───────────────────────────────────────────────────────────────
  getMyLoyalty: async (): Promise<LoyaltyMemberResponse> => {
    return api.get<LoyaltyMemberResponse>('/loyalty/me')
  },

  getMemberProfile: async (memberId: number): Promise<LoyaltyMemberProfile> => {
    return api.get<LoyaltyMemberProfile>(`/loyalty/member/${memberId}`)
  },

  getMemberByCustomer: async (customerId: number): Promise<LoyaltyMemberProfile> => {
    return api.get<LoyaltyMemberProfile>(`/loyalty/member/by-customer/${customerId}`)
  },

  // ── Admin ────────────────────────────────────────────────────────────────
  getDashboard: async (programId: number): Promise<LoyaltyDashboardMetrics> => {
    return api.get<LoyaltyDashboardMetrics>(`/loyalty/admin/dashboard?program_id=${programId}`)
  },

  listMembers: async (params?: {
    program_id: number
    skip?: number
    limit?: number
    search?: string
    tier?: LoyaltyTier
  }): Promise<PaginatedLoyaltyMembers> => {
    const p: Record<string, string> = {
      program_id: String(params?.program_id ?? 1),
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 20),
    }
    if (params?.search) p.search = params.search
    if (params?.tier) p.tier = params.tier
    const qs = new URLSearchParams(p).toString()
    return api.get<PaginatedLoyaltyMembers>(`/loyalty/admin/members?${qs}`)
  },

  adjustPoints: async (data: AdjustPointsRequest): Promise<{ new_balance: number; status: string }> => {
    return api.post<{ new_balance: number; status: string }>('/loyalty/admin/adjust', data)
  },

  // ── Rewards catalog ──────────────────────────────────────────────────────
  listRewards: async (programId: number): Promise<RewardsCatalogResponse[]> => {
    return api.get<RewardsCatalogResponse[]>(`/loyalty/admin/rewards?program_id=${programId}`)
  },

  createReward: async (data: RewardsCatalogCreate, programId: number): Promise<RewardsCatalogResponse> => {
    return api.post<RewardsCatalogResponse>(`/loyalty/admin/rewards?program_id=${programId}`, data)
  },

  updateReward: async (rewardId: number, data: RewardsCatalogUpdate): Promise<RewardsCatalogResponse> => {
    return api.put<RewardsCatalogResponse>(`/loyalty/admin/rewards/${rewardId}`, data)
  },

  // ── Flash offers ─────────────────────────────────────────────────────────
  listFlashOffers: async (): Promise<FlashOfferResponse[]> => {
    return api.get<FlashOfferResponse[]>('/loyalty/admin/flash-offers')
  },

  createFlashOffer: async (data: FlashOfferCreate): Promise<FlashOfferResponse> => {
    return api.post<FlashOfferResponse>('/loyalty/admin/flash-offers', data)
  },

  // ── Wallet ───────────────────────────────────────────────────────────────
  getApplePass: async (memberId: number): Promise<Blob> => {
    const resp = await fetch(`/api/v1/loyalty/pass/${memberId}/apple`, {
      credentials: 'include',
    })
    if (!resp.ok) throw new Error('Failed to download pass')
    return resp.blob()
  },

  // ── Export ───────────────────────────────────────────────────────────────
  exportCsv: async (type: 'members' | 'transactions' | 'redemptions', programId: number): Promise<Blob> => {
    const resp = await fetch(`/api/v1/loyalty/admin/export/${type}?program_id=${programId}`, {
      credentials: 'include',
    })
    if (!resp.ok) throw new Error('Export failed')
    return resp.blob()
  },
}
