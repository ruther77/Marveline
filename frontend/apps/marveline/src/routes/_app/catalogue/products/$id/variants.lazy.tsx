import { createLazyFileRoute } from '@tanstack/react-router'
import ProductVariantsPage from '@/pages/products/ProductVariantsPage'

export const Route = createLazyFileRoute('/_app/catalogue/products/$id/variants')({
  component: ProductVariantsPage,
})
