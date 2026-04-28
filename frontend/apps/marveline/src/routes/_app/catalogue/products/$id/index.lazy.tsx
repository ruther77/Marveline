import { createLazyFileRoute } from '@tanstack/react-router'
import ProductDetailPage from '@/pages/products/ProductDetailPage'

export const Route = createLazyFileRoute('/_app/catalogue/products/$id/')({
  component: ProductDetailPage,
})
