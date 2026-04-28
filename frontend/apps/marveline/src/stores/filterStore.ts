import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// ============================================
// Types
// ============================================

export interface DevisFilters {
  status: string[]
  customer_id: number | null
  date_from: string | null
  date_to: string | null
  search: string
}

export interface ReservationFilters {
  status: string[]
  customer_id: number | null
  event_type: string[]
  date_from: string | null
  date_to: string | null
  search: string
}

export interface VenteFilters {
  status: string[]
  customer_id: number | null
  date_from: string | null
  date_to: string | null
  search: string
}

export interface InvoiceFilters {
  status: string[]
  customer_id: number | null
  date_from: string | null
  date_to: string | null
  overdue_only: boolean
  search: string
}

export interface EventFilters {
  status: string[]
  date_from: string | null
  date_to: string | null
  search: string
}

export interface CatalogueFilters {
  category_id: number | null
  available_only: boolean
  search: string
}

// ============================================
// Defaults
// ============================================

const defaultDevis: DevisFilters = {
  status: [],
  customer_id: null,
  date_from: null,
  date_to: null,
  search: '',
}

const defaultReservation: ReservationFilters = {
  status: [],
  customer_id: null,
  event_type: [],
  date_from: null,
  date_to: null,
  search: '',
}

const defaultVente: VenteFilters = {
  status: [],
  customer_id: null,
  date_from: null,
  date_to: null,
  search: '',
}

const defaultInvoice: InvoiceFilters = {
  status: [],
  customer_id: null,
  date_from: null,
  date_to: null,
  overdue_only: false,
  search: '',
}

const defaultEvent: EventFilters = {
  status: [],
  date_from: null,
  date_to: null,
  search: '',
}

const defaultCatalogue: CatalogueFilters = {
  category_id: null,
  available_only: false,
  search: '',
}

// ============================================
// Page sizes (préférence utilisateur — seul élément persisté)
// ============================================

export interface PageSizes {
  devis: number
  reservation: number
  vente: number
  invoice: number
  event: number
  catalogue: number
}

const defaultPageSizes: PageSizes = {
  devis: 20,
  reservation: 20,
  vente: 20,
  invoice: 20,
  event: 20,
  catalogue: 20,
}

// ============================================
// State & Actions
// ============================================

interface FilterState {
  devis: DevisFilters
  reservation: ReservationFilters
  vente: VenteFilters
  invoice: InvoiceFilters
  event: EventFilters
  catalogue: CatalogueFilters
  pageSizes: PageSizes
}

interface FilterActions {
  setDevisFilters: (filters: Partial<DevisFilters>) => void
  setReservationFilters: (filters: Partial<ReservationFilters>) => void
  setVenteFilters: (filters: Partial<VenteFilters>) => void
  setInvoiceFilters: (filters: Partial<InvoiceFilters>) => void
  setEventFilters: (filters: Partial<EventFilters>) => void
  setCatalogueFilters: (filters: Partial<CatalogueFilters>) => void
  setPageSize: (module: keyof PageSizes, size: number) => void
  resetDevisFilters: () => void
  resetReservationFilters: () => void
  resetVenteFilters: () => void
  resetInvoiceFilters: () => void
  resetEventFilters: () => void
  resetCatalogueFilters: () => void
  resetAll: () => void
}

// ============================================
// Store
// ============================================

export const useFilterStore = create<FilterState & FilterActions>()(
  persist(
    (set) => ({
      devis: defaultDevis,
      reservation: defaultReservation,
      vente: defaultVente,
      invoice: defaultInvoice,
      event: defaultEvent,
      catalogue: defaultCatalogue,
      pageSizes: defaultPageSizes,

      setDevisFilters: (filters) =>
        set((state) => ({ devis: { ...state.devis, ...filters } })),
      setReservationFilters: (filters) =>
        set((state) => ({ reservation: { ...state.reservation, ...filters } })),
      setVenteFilters: (filters) =>
        set((state) => ({ vente: { ...state.vente, ...filters } })),
      setInvoiceFilters: (filters) =>
        set((state) => ({ invoice: { ...state.invoice, ...filters } })),
      setEventFilters: (filters) =>
        set((state) => ({ event: { ...state.event, ...filters } })),
      setCatalogueFilters: (filters) =>
        set((state) => ({ catalogue: { ...state.catalogue, ...filters } })),
      setPageSize: (module, size) =>
        set((state) => ({ pageSizes: { ...state.pageSizes, [module]: size } })),

      resetDevisFilters: () => set({ devis: defaultDevis }),
      resetReservationFilters: () => set({ reservation: defaultReservation }),
      resetVenteFilters: () => set({ vente: defaultVente }),
      resetInvoiceFilters: () => set({ invoice: defaultInvoice }),
      resetEventFilters: () => set({ event: defaultEvent }),
      resetCatalogueFilters: () => set({ catalogue: defaultCatalogue }),
      resetAll: () =>
        set({
          devis: defaultDevis,
          reservation: defaultReservation,
          vente: defaultVente,
          invoice: defaultInvoice,
          event: defaultEvent,
          catalogue: defaultCatalogue,
          // pageSizes intentionnellement non réinitialisé (préférence utilisateur)
        }),
    }),
    {
      name: 'marveline-filters',
      // Persister uniquement pageSizes (préférence utilisateur)
      // page, search, status, sort_* sont réinitialisés à chaque mount
      partialize: (state) => ({ pageSizes: state.pageSizes }),
    }
  )
)

// ============================================
// Hooks utilitaires
// ============================================

export const useDevisFilters = () => {
  const { devis, setDevisFilters, resetDevisFilters } = useFilterStore()
  const hasActiveFilters =
    devis.status.length > 0 ||
    devis.customer_id !== null ||
    devis.date_from !== null ||
    devis.date_to !== null ||
    devis.search !== ''
  return { filters: devis, set: setDevisFilters, reset: resetDevisFilters, hasActiveFilters }
}

export const useReservationFilters = () => {
  const { reservation, setReservationFilters, resetReservationFilters } = useFilterStore()
  const hasActiveFilters =
    reservation.status.length > 0 ||
    reservation.customer_id !== null ||
    reservation.event_type.length > 0 ||
    reservation.date_from !== null ||
    reservation.date_to !== null ||
    reservation.search !== ''
  return { filters: reservation, set: setReservationFilters, reset: resetReservationFilters, hasActiveFilters }
}

export const useVenteFilters = () => {
  const { vente, setVenteFilters, resetVenteFilters } = useFilterStore()
  const hasActiveFilters =
    vente.status.length > 0 ||
    vente.customer_id !== null ||
    vente.date_from !== null ||
    vente.date_to !== null ||
    vente.search !== ''
  return { filters: vente, set: setVenteFilters, reset: resetVenteFilters, hasActiveFilters }
}

export const useInvoiceFilters = () => {
  const { invoice, setInvoiceFilters, resetInvoiceFilters } = useFilterStore()
  const hasActiveFilters =
    invoice.status.length > 0 ||
    invoice.customer_id !== null ||
    invoice.date_from !== null ||
    invoice.date_to !== null ||
    invoice.overdue_only ||
    invoice.search !== ''
  return { filters: invoice, set: setInvoiceFilters, reset: resetInvoiceFilters, hasActiveFilters }
}

export const useEventFilters = () => {
  const { event, setEventFilters, resetEventFilters } = useFilterStore()
  const hasActiveFilters =
    event.status.length > 0 ||
    event.date_from !== null ||
    event.date_to !== null ||
    event.search !== ''
  return { filters: event, set: setEventFilters, reset: resetEventFilters, hasActiveFilters }
}

export const useCatalogueFilters = () => {
  const { catalogue, setCatalogueFilters, resetCatalogueFilters } = useFilterStore()
  const hasActiveFilters =
    catalogue.category_id !== null ||
    catalogue.available_only ||
    catalogue.search !== ''
  return { filters: catalogue, set: setCatalogueFilters, reset: resetCatalogueFilters, hasActiveFilters }
}
