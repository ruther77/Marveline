import { createLazyFileRoute } from '@tanstack/react-router'
import ProductsPage from '@/pages/products/ProductsPage'

export const Route = createLazyFileRoute('/_app/catalogue/products/')({
  component: ProductsPage,
})
