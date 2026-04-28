import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { DepartureInventory, ReturnInventory, DepartureCheckItem, DamageDeclaration } from '@/types'

// ============================================
// State & Actions
// ============================================

interface OperationsState {
  // Départ en cours (check départ réservation active)
  departureInventory: DepartureInventory | null
  departureLoading: boolean

  // Retour en cours
  returnInventory: ReturnInventory | null
  returnLoading: boolean

  // Réservation actuellement en check terrain
  activeReservationId: number | null

  // Codes QR scannés durant la session
  scannedCodes: string[]

  // Déclarations de dommages
  damageDeclarations: DamageDeclaration[]

  // Signature numérique (base64)
  signature: string | null
}

interface OperationsActions {
  setDepartureInventory: (inv: DepartureInventory | null) => void
  setDepartureLoading: (loading: boolean) => void
  updateDepartureItem: (line_id: number, patch: Partial<DepartureCheckItem>) => void

  setReturnInventory: (inv: ReturnInventory | null) => void
  setReturnLoading: (loading: boolean) => void

  setActiveReservationId: (id: number | null) => void

  addScannedCode: (code: string) => void
  markDamaged: (declaration: DamageDeclaration) => void
  removeDamage: (product_id: number) => void
  setSignature: (signature: string | null) => void

  clearSession: () => void
  reset: () => void
}

// ============================================
// Store — persisté complet (checklist terrain survit rechargement)
// ============================================

const initialState: OperationsState = {
  departureInventory: null,
  departureLoading: false,
  returnInventory: null,
  returnLoading: false,
  activeReservationId: null,
  scannedCodes: [],
  damageDeclarations: [],
  signature: null,
}

export const useOperationsStore = create<OperationsState & OperationsActions>()(
  persist(
    (set) => ({
      ...initialState,

      setDepartureInventory: (departureInventory) => set({ departureInventory }),
      setDepartureLoading: (departureLoading) => set({ departureLoading }),

      updateDepartureItem: (line_id, patch) =>
        set((state) => {
          if (!state.departureInventory) return state
          return {
            departureInventory: {
              ...state.departureInventory,
              items: (state.departureInventory.items ?? []).map((item) =>
                item.line_id === line_id ? { ...item, ...patch } : item
              ),
            },
          }
        }),

      setReturnInventory: (returnInventory) => set({ returnInventory }),
      setReturnLoading: (returnLoading) => set({ returnLoading }),

      setActiveReservationId: (activeReservationId) => set({ activeReservationId }),

      addScannedCode: (code) =>
        set((state) => ({
          scannedCodes: state.scannedCodes.includes(code)
            ? state.scannedCodes
            : [...state.scannedCodes, code],
        })),

      markDamaged: (declaration) =>
        set((state) => {
          const exists = state.damageDeclarations.findIndex(
            (d) => d.product_id === declaration.product_id
          )
          if (exists >= 0) {
            const updated = [...state.damageDeclarations]
            updated[exists] = declaration
            return { damageDeclarations: updated }
          }
          return { damageDeclarations: [...state.damageDeclarations, declaration] }
        }),

      removeDamage: (product_id) =>
        set((state) => ({
          damageDeclarations: state.damageDeclarations.filter(
            (d) => d.product_id !== product_id
          ),
        })),

      setSignature: (signature) => set({ signature }),

      clearSession: () =>
        set({
          scannedCodes: [],
          damageDeclarations: [],
          signature: null,
          activeReservationId: null,
          departureInventory: null,
          returnInventory: null,
        }),

      reset: () => set(initialState),
    }),
    {
      name: 'marveline-operations',
    }
  )
)

// ============================================
// Hooks utilitaires
// ============================================

export const useDepartureReadiness = () =>
  useOperationsStore((s) => {
    const inv = s.departureInventory
    if (!inv) return { allLoaded: false, allScanned: false, ready: false }
    const allLoaded = (inv.items ?? []).every(
      (item) => (item.quantity_loaded ?? item.quantity_expected) >= item.quantity_expected
    )
    return {
      allLoaded,
      allScanned: inv.all_scanned ?? false,
      ready: inv.ready_to_depart ?? false,
    }
  })
