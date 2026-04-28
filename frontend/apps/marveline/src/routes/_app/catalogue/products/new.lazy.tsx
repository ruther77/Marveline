import { createLazyFileRoute } from '@tanstack/react-router'
import ProductCreatePage from '@/pages/products/ProductCreatePage'

export const Route = createLazyFileRoute('/_app/catalogue/products/new')({
  component: ProductCreatePage,
})
