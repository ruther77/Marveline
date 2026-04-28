import { createLazyFileRoute } from '@tanstack/react-router'
import CatalogueBuilderPage from '@/pages/catalogue/CatalogueBuilderPage'

export const Route = createLazyFileRoute('/_app/catalogue/builder')({
  component: CatalogueBuilderPage,
})
