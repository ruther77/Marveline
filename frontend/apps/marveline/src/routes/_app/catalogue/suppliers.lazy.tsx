import { createLazyFileRoute } from '@tanstack/react-router'
import SuppliersPage from '@/pages/products/SuppliersPage'

export const Route = createLazyFileRoute('/_app/catalogue/suppliers')({
  component: SuppliersPage,
})
