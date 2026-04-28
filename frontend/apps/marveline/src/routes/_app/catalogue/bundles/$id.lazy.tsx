import { createLazyFileRoute } from '@tanstack/react-router'
import BundleDetailPage from '@/pages/products/BundleDetailPage'

export const Route = createLazyFileRoute('/_app/catalogue/bundles/$id')({
  component: BundleDetailPage,
})
