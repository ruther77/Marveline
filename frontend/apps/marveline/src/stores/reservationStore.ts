import { create } from 'zustand'
import type { ReservationList, ReservationDetailFull, ReservationStatus } from '@/types'

// ============================================
// Transitions (machine d'états)
// ============================================

const RESERVATION_TRANSITIONS: Record<ReservationStatus, ReservationStatus[]> = {
  draft:            ['confirmed', 'cancelled'],
  confirmed:        ['confirmed_risk', 'pre_check', 'delivered', 'cancelled'],
  confirmed_risk:   ['confirmed', 'pre_check', 'delivered', 'cancelled'],
  pre_check:        ['delivered', 'cancelled'],
  delivered:        ['extended', 'returned', 'cancelled'],
  extended:         ['extended', 'returned', 'cancelled'],
  returned:         ['returned_dispute', 'completed'],
  returned_dispute: ['returned'],
  completed:        [],
  cancelled:        [],
}

export function canReservationTransition(from: ReservationStatus, to: ReservationStatus): boolean {
  return RESERVATION_TRANSITIONS[from]?.includes(to) ?? false
}

export function assertReservationTransition(from: ReservationStatus, to: ReservationStatus): void {
  if (!canReservationTransition(from, to)) {
    throw new Error(`Transition invalide : ${from} → ${to}`)
  }
}

// ============================================
// State & Actions
// ============================================

interface ReservationState {
  list: ReservationList[]
  total: number
  selectedId: number | null
  detail: ReservationDetailFull | null
  detailLoading: boolean
}

interface ReservationActions {
  setList: (items: ReservationList[], total: number) => void
  upsertListItem: (item: ReservationList) => void
  removeListItem: (id: number) => void
  setSelectedId: (id: number | null) => void
  setDetail: (detail: ReservationDetailFull | null) => void
  setDetailLoading: (loading: boolean) => void
  transition: (from: ReservationStatus, to: ReservationStatus) => void
  canTransition: (from: ReservationStatus, to: ReservationStatus) => boolean
  reset: () => void
}

// ============================================
// Store
// ============================================

const initialState: ReservationState = {
  list: [],
  total: 0,
  selectedId: null,
  detail: null,
  detailLoading: false,
}

export const useReservationStore = create<ReservationState & ReservationActions>()((set) => ({
  ...initialState,

  setList: (items, total) => set({ list: items, total }),

  upsertListItem: (item) =>
    set((state) => {
      const exists = state.list.some((r) => r.id === item.id)
      return {
        list: exists
          ? state.list.map((r) => (r.id === item.id ? item : r))
          : [item, ...state.list],
        total: exists ? state.total : state.total + 1,
      }
    }),

  removeListItem: (id) =>
    set((state) => ({
      list: state.list.filter((r) => r.id !== id),
      total: Math.max(0, state.total - 1),
      selectedId: state.selectedId === id ? null : state.selectedId,
      detail: state.detail?.id === id ? null : state.detail,
    })),

  setSelectedId: (selectedId) => set({ selectedId }),
  setDetail: (detail) => set({ detail }),
  setDetailLoading: (detailLoading) => set({ detailLoading }),

  transition: (from, to) => {
    assertReservationTransition(from, to)
  },

  canTransition: (from, to) => canReservationTransition(from, to),

  reset: () => set(initialState),
}))
