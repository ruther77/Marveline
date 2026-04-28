import { createLazyFileRoute } from '@tanstack/react-router'
import ProductImportPage from '@/pages/products/ProductImportPage'

export const Route = createLazyFileRoute('/_app/catalogue/import')({
  component: ProductImportPage,
})
