import { create } from 'zustand'
import type { InvoiceListItem, InvoiceDetailFull, InvoiceStatus } from '@/types'

// ============================================
// Transitions (machine d'états)
// ============================================

const INVOICE_TRANSITIONS: Record<string, string[]> = {
  draft:    ['sent', 'cancelled'],
  sent:     ['paid', 'overdue', 'cancelled'],
  overdue:  ['paid', 'cancelled'],
  paid:     [],
  cancelled: [],
}

export function canInvoiceTransition(from: string, to: string): boolean {
  return INVOICE_TRANSITIONS[from]?.includes(to) ?? false
}

export function assertInvoiceTransition(from: string, to: string): void {
  if (!canInvoiceTransition(from, to)) {
    throw new Error(`Transition invalide : ${from} → ${to}`)
  }
}

// ============================================
// PaymentDraft
// ============================================

export interface PaymentDraft {
  amount_euros: string           // saisie string input
  amount_cents: number           // Math.round(parseFloat(amount_euros) * 100) — auto-calculé
  payment_method: string | null
  payment_date: string
  notes: string
}

const defaultPaymentDraft: PaymentDraft = {
  amount_euros: '',
  amount_cents: 0,
  payment_method: null,
  payment_date: new Date().toISOString().slice(0, 10),
  notes: '',
}

// ============================================
// State & Actions
// ============================================

interface InvoiceState {
  list: InvoiceListItem[]
  total: number
  overdueCount: number
  selectedId: number | null
  detail: InvoiceDetailFull | null
  detailLoading: boolean
  paymentDraft: PaymentDraft
}

interface InvoiceActions {
  setList: (items: InvoiceListItem[], total: number) => void
  setOverdueCount: (count: number) => void
  upsertListItem: (item: InvoiceListItem) => void
  removeListItem: (id: number) => void
  setSelectedId: (id: number | null) => void
  setDetail: (detail: InvoiceDetailFull | null) => void
  setDetailLoading: (loading: boolean) => void
  transition: (from: InvoiceStatus | string, to: InvoiceStatus | string) => void
  canTransition: (from: InvoiceStatus | string, to: InvoiceStatus | string) => boolean
  updatePaymentDraft: (updates: Partial<Omit<PaymentDraft, 'amount_cents'>>) => void
  clearPaymentDraft: () => void
  reset: () => void
}

// ============================================
// Store
// ============================================

const initialState: InvoiceState = {
  list: [],
  total: 0,
  overdueCount: 0,
  selectedId: null,
  detail: null,
  detailLoading: false,
  paymentDraft: defaultPaymentDraft,
}

export const useInvoiceStore = create<InvoiceState & InvoiceActions>()((set) => ({
  ...initialState,

  setList: (items, total) => set({ list: items, total }),
  setOverdueCount: (overdueCount) => set({ overdueCount }),

  upsertListItem: (item) =>
    set((state) => {
      const exists = state.list.some((i) => i.id === item.id)
      return {
        list: exists
          ? state.list.map((i) => (i.id === item.id ? item : i))
          : [item, ...state.list],
        total: exists ? state.total : state.total + 1,
      }
    }),

  removeListItem: (id) =>
    set((state) => ({
      list: state.list.filter((i) => i.id !== id),
      total: Math.max(0, state.total - 1),
      selectedId: state.selectedId === id ? null : state.selectedId,
      detail: state.detail?.id === id ? null : state.detail,
    })),

  setSelectedId: (selectedId) => set({ selectedId }),
  setDetail: (detail) => set({ detail }),
  setDetailLoading: (detailLoading) => set({ detailLoading }),

  transition: (from, to) => {
    assertInvoiceTransition(from, to)
  },

  canTransition: (from, to) => canInvoiceTransition(from, to),

  updatePaymentDraft: (updates) =>
    set((state) => {
      const merged = { ...state.paymentDraft, ...updates }
      const parsed = parseFloat(merged.amount_euros)
      const amount_cents = isNaN(parsed) || parsed < 0 ? 0 : Math.round(parsed * 100)
      return { paymentDraft: { ...merged, amount_cents } }
    }),

  clearPaymentDraft: () => set({ paymentDraft: defaultPaymentDraft }),

  reset: () => set(initialState),
}))
