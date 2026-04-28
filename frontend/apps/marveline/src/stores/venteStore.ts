import { create } from 'zustand'
import type { VenteListItem, VenteDetailFull, VenteStatus } from '@/types'

// ============================================
// Transitions (machine d'états)
// ============================================

const VENTE_TRANSITIONS: Record<string, string[]> = {
  draft:        ['pending', 'cancelled'],
  pending:      ['deposit_paid', 'fully_paid', 'overdue'],
  deposit_paid: ['fully_paid', 'overdue'],
  overdue:      ['fully_paid', 'refunded'],
  fully_paid:   ['refunded'],
  refunded:     [],
  cancelled:    [],
}

export function canVenteTransition(from: string, to: string): boolean {
  return VENTE_TRANSITIONS[from]?.includes(to) ?? false
}

export function assertVenteTransition(from: string, to: string): void {
  if (!canVenteTransition(from, to)) {
    throw new Error(`Transition invalide : ${from} → ${to}`)
  }
}

// ============================================
// State & Actions
// ============================================

interface VenteState {
  list: VenteListItem[]
  total: number
  selectedId: number | null
  detail: VenteDetailFull | null
  detailLoading: boolean
}

interface VenteActions {
  setList: (items: VenteListItem[], total: number) => void
  upsertListItem: (item: VenteListItem) => void
  removeListItem: (id: number) => void
  setSelectedId: (id: number | null) => void
  setDetail: (detail: VenteDetailFull | null) => void
  setDetailLoading: (loading: boolean) => void
  transition: (from: VenteStatus | string, to: VenteStatus | string) => void
  canTransition: (from: VenteStatus | string, to: VenteStatus | string) => boolean
  reset: () => void
}

// ============================================
// Store
// ============================================

const initialState: VenteState = {
  list: [],
  total: 0,
  selectedId: null,
  detail: null,
  detailLoading: false,
}

export const useVenteStore = create<VenteState & VenteActions>()((set) => ({
  ...initialState,

  setList: (items, total) => set({ list: items, total }),

  upsertListItem: (item) =>
    set((state) => {
      const exists = state.list.some((v) => v.id === item.id)
      return {
        list: exists
          ? state.list.map((v) => (v.id === item.id ? item : v))
          : [item, ...state.list],
        total: exists ? state.total : state.total + 1,
      }
    }),

  removeListItem: (id) =>
    set((state) => ({
      list: state.list.filter((v) => v.id !== id),
      total: Math.max(0, state.total - 1),
      selectedId: state.selectedId === id ? null : state.selectedId,
      detail: state.detail?.id === id ? null : state.detail,
    })),

  setSelectedId: (selectedId) => set({ selectedId }),
  setDetail: (detail) => set({ detail }),
  setDetailLoading: (detailLoading) => set({ detailLoading }),

  transition: (from, to) => {
    assertVenteTransition(from, to)
  },

  canTransition: (from, to) => canVenteTransition(from, to),

  reset: () => set(initialState),
}))
