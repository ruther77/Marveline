import { create } from 'zustand'
import type { DevisListItem, DevisDetailFull, DevisStatus } from '@/types'
import { useCartStore } from './cartStore'

// ============================================
// Transitions (machine d'états)
// ============================================

const DEVIS_TRANSITIONS: Record<string, string[]> = {
  draft:           ['sent', 'cancelled'],
  sent:            ['negotiation', 'accepted', 'refused', 'expired'],
  negotiation:     ['accepted', 'refused', 'expired', 'version_pending'],
  version_pending: ['negotiation', 'accepted', 'refused'],
  accepted:        ['converted', 'cancelled'],
  refused:         [],
  expired:         ['draft'],
  converted:       [],
  cancelled:       [],
}

export function canDevisTransition(from: string, to: string): boolean {
  return DEVIS_TRANSITIONS[from]?.includes(to) ?? false
}

export function assertDevisTransition(from: string, to: string): void {
  if (!canDevisTransition(from, to)) {
    throw new Error(`Transition invalide : ${from} → ${to}`)
  }
}

// ============================================
// Stepper
// ============================================

export type DevisStep = 'client' | 'articles' | 'recap'

const DEVIS_STEPS: DevisStep[] = ['client', 'articles', 'recap']

// ============================================
// State & Actions
// ============================================

interface DevisState {
  list: DevisListItem[]
  total: number
  selectedId: number | null
  detail: DevisDetailFull | null
  detailLoading: boolean
  // Stepper création
  currentStep: DevisStep
}

interface DevisActions {
  setList: (items: DevisListItem[], total: number) => void
  upsertListItem: (item: DevisListItem) => void
  removeListItem: (id: number) => void
  setSelectedId: (id: number | null) => void
  setDetail: (detail: DevisDetailFull | null) => void
  setDetailLoading: (loading: boolean) => void
  transition: (from: DevisStatus | string, to: DevisStatus | string) => void
  canTransition: (from: DevisStatus | string, to: DevisStatus | string) => boolean
  // Stepper
  setStep: (step: DevisStep) => void
  nextStep: () => void
  prevStep: () => void
  reset: () => void
}

// ============================================
// Store (pas de persist — données serveur)
// ============================================

const initialState: DevisState = {
  list: [],
  total: 0,
  selectedId: null,
  detail: null,
  detailLoading: false,
  currentStep: 'client',
}

export const useDevisStore = create<DevisState & DevisActions>()((set, get) => ({
  ...initialState,

  setList: (items, total) => set({ list: items, total }),

  upsertListItem: (item) =>
    set((state) => {
      const exists = state.list.some((d) => d.id === item.id)
      return {
        list: exists
          ? state.list.map((d) => (d.id === item.id ? item : d))
          : [item, ...state.list],
        total: exists ? state.total : state.total + 1,
      }
    }),

  removeListItem: (id) =>
    set((state) => ({
      list: state.list.filter((d) => d.id !== id),
      total: Math.max(0, state.total - 1),
      selectedId: state.selectedId === id ? null : state.selectedId,
      detail: state.detail?.id === id ? null : state.detail,
    })),

  setSelectedId: (selectedId) => set({ selectedId }),
  setDetail: (detail) => set({ detail }),
  setDetailLoading: (detailLoading) => set({ detailLoading }),

  transition: (from, to) => {
    assertDevisTransition(from, to)
  },

  canTransition: (from, to) => canDevisTransition(from, to),

  setStep: (step) => set({ currentStep: step }),

  nextStep: () =>
    set((state) => {
      const idx = DEVIS_STEPS.indexOf(state.currentStep)
      if (idx < DEVIS_STEPS.length - 1) {
        return { currentStep: DEVIS_STEPS[idx + 1] }
      }
      return state
    }),

  prevStep: () =>
    set((state) => {
      const idx = DEVIS_STEPS.indexOf(state.currentStep)
      if (idx > 0) {
        return { currentStep: DEVIS_STEPS[idx - 1] }
      }
      return state
    }),

  reset: () => {
    useCartStore.getState().reset()
    set(initialState)
  },
}))

// ============================================
// Helper : assembler DevisCreate depuis cartStore
// ============================================

export function buildDevisCreate() {
  const cart = useCartStore.getState()
  return {
    customer_id: cart.customer_id,
    event_date: cart.event_date,
    delivery_date: cart.delivery_date,
    return_date: cart.return_date,
    event_location: cart.event_location,
    notes: cart.notes,
    valid_until: cart.valid_until,
    lines: cart.lines.map((l) => ({
      product_id: l.product_id,
      quantity: l.quantity,
      unit_price_cents: l.unit_price_cents,
    })),
  }
}
