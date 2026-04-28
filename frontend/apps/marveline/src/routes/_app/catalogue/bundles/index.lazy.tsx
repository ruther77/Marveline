import { createLazyFileRoute } from '@tanstack/react-router'
import BundlesPage from '@/pages/products/BundlesPage'

export const Route = createLazyFileRoute('/_app/catalogue/bundles/')({
  component: BundlesPage,
})
