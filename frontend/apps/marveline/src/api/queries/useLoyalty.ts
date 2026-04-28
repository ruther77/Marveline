import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { loyaltyApi } from '../loyalty'
import type {
  LoyaltyMemberCreate,
  CreditRequest,
  RedeemRequest,
  AdjustPointsRequest,
  RewardsCatalogCreate,
  RewardsCatalogUpdate,
  FlashOfferCreate,
  RevenueCreditRequest,
  LoyaltyTier,
} from '@/types/loyalty'

// ── Dashboard ────────────────────────────────────────────────────────────────

export function useLoyaltyDashboard(programId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.loyalty.dashboard(programId),
    queryFn: () => loyaltyApi.getDashboard(programId),
    enabled,
    staleTime: 60_000,
  })
}

// ── Members ──────────────────────────────────────────────────────────────────

export function useLoyaltyMembers(params?: {
  program_id: number
  skip?: number
  limit?: number
  search?: string
  tier?: LoyaltyTier
}, enabled = true) {
  return useQuery({
    queryKey: queryKeys.loyalty.memberList(params ?? {}),
    queryFn: () => loyaltyApi.listMembers(params),
    enabled,
  })
}

export function useLoyaltyMemberProfile(memberId: number | null) {
  return useQuery({
    queryKey: queryKeys.loyalty.memberProfile(memberId!),
    queryFn: () => loyaltyApi.getMemberProfile(memberId!),
    enabled: memberId !== null,
  })
}

export function useLoyaltyByCustomer(customerId: number | null) {
  return useQuery({
    queryKey: ['loyalty', 'by-customer', customerId] as const,
    queryFn: () => loyaltyApi.getMemberByCustomer(customerId!),
    enabled: customerId !== null && customerId > 0,
    retry: false,
  })
}

export function useMyLoyalty(enabled = true) {
  return useQuery({
    queryKey: queryKeys.loyalty.me(),
    queryFn: () => loyaltyApi.getMyLoyalty(),
    enabled,
    staleTime: 5 * 60_000,
  })
}

// ── Join ──────────────────────────────────────────────────────────────────────

export function useJoinLoyalty() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: LoyaltyMemberCreate) => loyaltyApi.join(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.me() })
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.members() })
    },
  })
}

// ── Scan ──────────────────────────────────────────────────────────────────────

export function useLoyaltyScan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (barcode: string) => loyaltyApi.scan({ barcode }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.me() })
    },
  })
}

// ── Credit ────────────────────────────────────────────────────────────────────

export function useCreditPoints() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CreditRequest) => loyaltyApi.creditPoints(data),
    onSuccess: (_result, vars) => {
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.memberProfile(vars.member_id) })
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.dashboard(0) })
    },
  })
}

export function useCreditRevenue() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: RevenueCreditRequest) => loyaltyApi.creditRevenue(data),
    onSuccess: (_result, vars) => {
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.memberProfile(vars.member_id) })
    },
  })
}

// ── Redeem ────────────────────────────────────────────────────────────────────

export function useRedeemReward() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: RedeemRequest) => loyaltyApi.redeem(data),
    onSuccess: (_result, vars) => {
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.memberProfile(vars.member_id) })
    },
  })
}

// ── Adjust ────────────────────────────────────────────────────────────────────

export function useAdjustPoints() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: AdjustPointsRequest) => loyaltyApi.adjustPoints(data),
    onSuccess: (_result, vars) => {
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.memberProfile(vars.member_id) })
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.members() })
    },
  })
}

// ── Rewards catalog ──────────────────────────────────────────────────────────

export function useLoyaltyRewards(programId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.loyalty.rewards(programId),
    queryFn: () => loyaltyApi.listRewards(programId),
    enabled,
  })
}

export function useCreateReward(programId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: RewardsCatalogCreate) => loyaltyApi.createReward(data, programId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.rewards(programId) })
    },
  })
}

export function useUpdateReward(programId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: RewardsCatalogUpdate }) =>
      loyaltyApi.updateReward(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.rewards(programId) })
    },
  })
}

// ── Flash offers ─────────────────────────────────────────────────────────────

export function useLoyaltyFlashOffers(enabled = true) {
  return useQuery({
    queryKey: queryKeys.loyalty.flashOffers(),
    queryFn: () => loyaltyApi.listFlashOffers(),
    enabled,
  })
}

export function useCreateFlashOffer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: FlashOfferCreate) => loyaltyApi.createFlashOffer(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.loyalty.flashOffers() })
    },
  })
}
