import { createLazyFileRoute } from '@tanstack/react-router'
import CatalogueAvailabilityPage from '@/pages/products/CatalogueAvailabilityPage'

export const Route = createLazyFileRoute('/_app/catalogue/availability')({
  component: CatalogueAvailabilityPage,
})
