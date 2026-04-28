import { createLazyFileRoute } from '@tanstack/react-router'
import SupplierOrdersPage from '@/pages/suppliers/SupplierOrdersPage'

export const Route = createLazyFileRoute('/_app/catalogue/supplier-orders')({
  component: SupplierOrdersPage,
})
