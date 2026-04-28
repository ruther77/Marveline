import { createLazyFileRoute } from '@tanstack/react-router'
import CatalogueSearchPage from '@/pages/products/CatalogueSearchPage'

export const Route = createLazyFileRoute('/_app/catalogue/search')({
  component: CatalogueSearchPage,
})
