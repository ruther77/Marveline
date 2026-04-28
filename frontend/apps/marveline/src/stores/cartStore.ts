import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { generateUUID } from '@/utils/uuid'

// ============================================
// Types
// ============================================

export interface CartLine {
  id: string                 // UUID local
  product_id?: number
  bundle_id?: number
  product_name: string
  category_id?: number
  quantity: number
  unit_price_cents: number   // TOUJOURS centimes
  subtotal_cents: number     // quantity * unit_price_cents (auto-calculé)
  available_quantity: number
}

export type CartMode = 'devis' | 'reservation'

interface CartState {
  mode: CartMode
  lines: CartLine[]
  // Métadonnées du contexte en cours
  customer_id: number | null
  event_date: string | null
  delivery_date: string | null
  return_date: string | null
  event_location: string | null
  valid_until: string | null
  notes: string
  // Livraison
  delivery_method: 'self' | 'carrier' | 'pickup' | null
  delivery_fee_cents: number
  carrier_name: string | null
  carrier_code: string | null
  delivery_address: string | null
  delivery_city: string | null
  delivery_postal_code: string | null
  delivery_zone_id: number | null
  delivery_instructions: string | null
}

interface CartActions {
  setMode: (mode: CartMode) => void
  addLine: (line: Omit<CartLine, 'id' | 'subtotal_cents'>) => void
  updateLine: (lineId: string, updates: Partial<Omit<CartLine, 'id' | 'subtotal_cents'>>) => void
  removeLine: (lineId: string) => void
  clearLines: () => void
  setCustomer: (customer_id: number | null) => void
  setEventInfo: (info: {
    event_date?: string | null
    delivery_date?: string | null
    return_date?: string | null
    event_location?: string | null
    valid_until?: string | null
  }) => void
  setDeliveryInfo: (info: {
    delivery_method?: 'self' | 'carrier' | 'pickup' | null
    delivery_fee_cents?: number
    carrier_name?: string | null
    carrier_code?: string | null
    delivery_address?: string | null
    delivery_city?: string | null
    delivery_postal_code?: string | null
    delivery_zone_id?: number | null
    delivery_instructions?: string | null
  }) => void
  setNotes: (notes: string) => void
  getTotalCents: () => number
  getLineCount: () => number
  hasProduct: (product_id: number) => boolean
  hasBundle: (bundle_id: number) => boolean
  reset: () => void
}

// ============================================
// Helpers
// ============================================

const calcSubtotal = (quantity: number, unit_price_cents: number): number =>
  Math.round(quantity * unit_price_cents)

// ============================================
// Store — persisté complet (panier survit au rechargement)
// ============================================

const initialState: CartState = {
  mode: 'devis',
  lines: [],
  customer_id: null,
  event_date: null,
  delivery_date: null,
  return_date: null,
  event_location: null,
  valid_until: null,
  notes: '',
  delivery_method: null,
  delivery_fee_cents: 0,
  carrier_name: null,
  carrier_code: null,
  delivery_address: null,
  delivery_city: null,
  delivery_postal_code: null,
  delivery_zone_id: null,
  delivery_instructions: null,
}

export const useCartStore = create<CartState & CartActions>()(
  persist(
    (set, get) => ({
      ...initialState,

      setMode: (mode) => set({ mode }),

      addLine: (line) => {
        const matchKey = line.bundle_id
          ? (l: CartLine) => l.bundle_id === line.bundle_id
          : (l: CartLine) => l.product_id === line.product_id
        const existing = get().lines.find(matchKey)
        if (existing) {
          set((state) => ({
            lines: state.lines.map((l) =>
              matchKey(l)
                ? {
                    ...l,
                    quantity: l.quantity + line.quantity,
                    subtotal_cents: calcSubtotal(l.quantity + line.quantity, l.unit_price_cents),
                  }
                : l
            ),
          }))
        } else {
          set((state) => ({
            lines: [
              ...state.lines,
              {
                ...line,
                id: generateUUID(),
                subtotal_cents: calcSubtotal(line.quantity, line.unit_price_cents),
              },
            ],
          }))
        }
      },

      updateLine: (lineId, updates) => {
        set((state) => ({
          lines: state.lines.map((l) => {
            if (l.id !== lineId) return l
            const merged = { ...l, ...updates }
            return { ...merged, subtotal_cents: calcSubtotal(merged.quantity, merged.unit_price_cents) }
          }),
        }))
      },

      removeLine: (lineId) =>
        set((state) => ({ lines: state.lines.filter((l) => l.id !== lineId) })),

      clearLines: () => set({ lines: [] }),

      setCustomer: (customer_id) => set({ customer_id }),

      setEventInfo: (info) => set((state) => ({ ...state, ...info })),

      setDeliveryInfo: (info) => set((state) => ({ ...state, ...info })),

      setNotes: (notes) => set({ notes }),

      getTotalCents: () =>
        get().lines.reduce((acc, l) => acc + l.subtotal_cents, 0),

      getLineCount: () => get().lines.length,

      hasProduct: (product_id) =>
        get().lines.some((l) => l.product_id === product_id),

      hasBundle: (bundle_id) =>
        get().lines.some((l) => l.bundle_id === bundle_id),

      reset: () => set(initialState),
    }),
    {
      name: 'marveline-cart',
    }
  )
)

// ============================================
// Hooks utilitaires
// ============================================

export const useCartTotals = () => {
  const lines = useCartStore((s) => s.lines)
  const total_cents = lines.reduce((acc, l) => acc + l.subtotal_cents, 0)
  const item_count = lines.reduce((acc, l) => acc + l.quantity, 0)
  const line_count = lines.length
  return { total_cents, item_count, line_count, isEmpty: line_count === 0 }
}

export const useCartLine = (product_id: number) =>
  useCartStore((s) => s.lines.find((l) => l.product_id === product_id))

export const useCartBundleLine = (bundle_id: number) =>
  useCartStore((s) => s.lines.find((l) => l.bundle_id === bundle_id))
