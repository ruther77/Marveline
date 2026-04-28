/**
 * Tests unitaires pour stores/filterStore.ts
 * Utilise Zustand directement — pas de rendu React nécessaire.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useFilterStore } from '../filterStore'

// Reset le store avant chaque test (évite la contamination entre tests)
beforeEach(() => {
  useFilterStore.getState().resetAll()
  // Reset les page sizes aussi
  useFilterStore.setState({ pageSizes: { devis: 20, reservation: 20, vente: 20, invoice: 20, event: 20, catalogue: 20 } })
})

describe('filterStore - état initial', () => {
  it('devis: status vide, pas de customer, pas de dates', () => {
    const { devis } = useFilterStore.getState()
    expect(devis.status).toHaveLength(0)
    expect(devis.customer_id).toBeNull()
    expect(devis.date_from).toBeNull()
    expect(devis.search).toBe('')
  })

  it('pageSizes: toutes à 20 par défaut', () => {
    const { pageSizes } = useFilterStore.getState()
    expect(pageSizes.devis).toBe(20)
    expect(pageSizes.reservation).toBe(20)
    expect(pageSizes.invoice).toBe(20)
  })
})

describe('filterStore - setDevisFilters', () => {
  it('met à jour les filtres devis partiellement', () => {
    useFilterStore.getState().setDevisFilters({ status: ['draft', 'sent'], customer_id: 5 })

    const { devis } = useFilterStore.getState()
    expect(devis.status).toEqual(['draft', 'sent'])
    expect(devis.customer_id).toBe(5)
    expect(devis.search).toBe('') // non modifié
  })

  it('met à jour la recherche', () => {
    useFilterStore.getState().setDevisFilters({ search: 'dupont' })

    expect(useFilterStore.getState().devis.search).toBe('dupont')
  })
})

describe('filterStore - setReservationFilters', () => {
  it('filtre par status et dates', () => {
    useFilterStore.getState().setReservationFilters({
      status: ['confirmed'],
      date_from: '2026-03-01',
      date_to: '2026-03-31',
    })

    const { reservation } = useFilterStore.getState()
    expect(reservation.status).toEqual(['confirmed'])
    expect(reservation.date_from).toBe('2026-03-01')
    expect(reservation.date_to).toBe('2026-03-31')
    expect(reservation.customer_id).toBeNull() // non modifié
  })
})

describe('filterStore - setVenteFilters / setInvoiceFilters', () => {
  it('filtre ventes par customer_id', () => {
    useFilterStore.getState().setVenteFilters({ customer_id: 10 })

    expect(useFilterStore.getState().vente.customer_id).toBe(10)
  })

  it('filtre factures avec overdue_only', () => {
    useFilterStore.getState().setInvoiceFilters({ overdue_only: true })

    expect(useFilterStore.getState().invoice.overdue_only).toBe(true)
  })
})

describe('filterStore - setEventFilters / setCatalogueFilters', () => {
  it('filtre événements par status', () => {
    useFilterStore.getState().setEventFilters({ status: ['incident'] })

    expect(useFilterStore.getState().event.status).toEqual(['incident'])
  })

  it('filtre catalogue avec available_only', () => {
    useFilterStore.getState().setCatalogueFilters({ available_only: true, category_id: 3 })

    const { catalogue } = useFilterStore.getState()
    expect(catalogue.available_only).toBe(true)
    expect(catalogue.category_id).toBe(3)
  })
})

describe('filterStore - setPageSize', () => {
  it('modifie la taille de page pour un module', () => {
    useFilterStore.getState().setPageSize('devis', 50)

    expect(useFilterStore.getState().pageSizes.devis).toBe(50)
    expect(useFilterStore.getState().pageSizes.reservation).toBe(20) // non modifié
  })
})

describe('filterStore - reset individuels', () => {
  it('resetDevisFilters sans toucher les autres', () => {
    useFilterStore.getState().setDevisFilters({ search: 'test', customer_id: 5 })
    useFilterStore.getState().setVenteFilters({ customer_id: 10 })

    useFilterStore.getState().resetDevisFilters()

    expect(useFilterStore.getState().devis.search).toBe('')
    expect(useFilterStore.getState().devis.customer_id).toBeNull()
    expect(useFilterStore.getState().vente.customer_id).toBe(10) // non touché
  })

  it('resetReservationFilters', () => {
    useFilterStore.getState().setReservationFilters({ status: ['confirmed'], event_type: ['wedding'] })
    useFilterStore.getState().resetReservationFilters()

    const { reservation } = useFilterStore.getState()
    expect(reservation.status).toHaveLength(0)
    expect(reservation.event_type).toHaveLength(0)
  })

  it('resetInvoiceFilters', () => {
    useFilterStore.getState().setInvoiceFilters({ overdue_only: true, search: 'test' })
    useFilterStore.getState().resetInvoiceFilters()

    expect(useFilterStore.getState().invoice.overdue_only).toBe(false)
    expect(useFilterStore.getState().invoice.search).toBe('')
  })

  it('resetCatalogueFilters', () => {
    useFilterStore.getState().setCatalogueFilters({ available_only: true, category_id: 5 })
    useFilterStore.getState().resetCatalogueFilters()

    expect(useFilterStore.getState().catalogue.available_only).toBe(false)
    expect(useFilterStore.getState().catalogue.category_id).toBeNull()
  })
})

describe('filterStore - resetAll', () => {
  it('réinitialise tous les filtres', () => {
    useFilterStore.getState().setDevisFilters({ search: 'a', customer_id: 1 })
    useFilterStore.getState().setVenteFilters({ customer_id: 2 })
    useFilterStore.getState().setInvoiceFilters({ overdue_only: true })
    useFilterStore.getState().setPageSize('devis', 50)

    useFilterStore.getState().resetAll()

    const state = useFilterStore.getState()
    expect(state.devis.search).toBe('')
    expect(state.devis.customer_id).toBeNull()
    expect(state.vente.customer_id).toBeNull()
    expect(state.invoice.overdue_only).toBe(false)
    // pageSizes NON réinitialisé (préférence utilisateur)
    expect(state.pageSizes.devis).toBe(50)
  })
})
