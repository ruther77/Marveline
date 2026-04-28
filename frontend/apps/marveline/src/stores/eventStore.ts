import { create } from 'zustand'
import type { EventListItem, EventDetailFull, EventStatus } from '@/types'

// ============================================
// Transitions (machine d'états)
// ============================================

const EVENT_TRANSITIONS: Record<string, string[]> = {
  planned:     ['risk', 'in_progress', 'cancelled'],
  risk:        ['planned', 'in_progress', 'cancelled'],
  in_progress: ['incident', 'returned', 'cancelled'],
  incident:    ['in_progress', 'returned'],
  returned:    ['damage', 'closed'],
  damage:      ['closed'],
  cancelled:   [],
  closed:      [],
}

export function canEventTransition(from: string, to: string): boolean {
  return EVENT_TRANSITIONS[from]?.includes(to) ?? false
}

export function assertEventTransition(from: string, to: string): void {
  if (!canEventTransition(from, to)) {
    throw new Error(`Transition invalide : ${from} → ${to}`)
  }
}

// ============================================
// State & Actions
// ============================================

interface EventStoreState {
  list: EventListItem[]
  total: number
  selectedId: number | null
  detail: EventDetailFull | null
  detailLoading: boolean
}

interface EventStoreActions {
  setList: (items: EventListItem[], total: number) => void
  upsertListItem: (item: EventListItem) => void
  removeListItem: (id: number) => void
  setSelectedId: (id: number | null) => void
  setDetail: (detail: EventDetailFull | null) => void
  setDetailLoading: (loading: boolean) => void
  transition: (from: EventStatus | string, to: EventStatus | string) => void
  canTransition: (from: EventStatus | string, to: EventStatus | string) => boolean
  reset: () => void
}

// ============================================
// Store
// ============================================

const initialState: EventStoreState = {
  list: [],
  total: 0,
  selectedId: null,
  detail: null,
  detailLoading: false,
}

export const useEventStore = create<EventStoreState & EventStoreActions>()((set) => ({
  ...initialState,

  setList: (items, total) => set({ list: items, total }),

  upsertListItem: (item) =>
    set((state) => {
      const exists = state.list.some((e) => e.id === item.id)
      return {
        list: exists
          ? state.list.map((e) => (e.id === item.id ? item : e))
          : [item, ...state.list],
        total: exists ? state.total : state.total + 1,
      }
    }),

  removeListItem: (id) =>
    set((state) => ({
      list: state.list.filter((e) => e.id !== id),
      total: Math.max(0, state.total - 1),
      selectedId: state.selectedId === id ? null : state.selectedId,
      detail: state.detail?.id === id ? null : state.detail,
    })),

  setSelectedId: (selectedId) => set({ selectedId }),
  setDetail: (detail) => set({ detail }),
  setDetailLoading: (detailLoading) => set({ detailLoading }),

  transition: (from, to) => {
    assertEventTransition(from, to)
  },

  canTransition: (from, to) => canEventTransition(from, to),

  reset: () => set(initialState),
}))
