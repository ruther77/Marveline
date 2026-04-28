import { createLazyFileRoute } from '@tanstack/react-router'
import ProductToolsPage from '@/pages/products/ProductToolsPage'

export const Route = createLazyFileRoute('/_app/catalogue/tools')({
  component: ProductToolsPage,
})
