import { createLazyFileRoute } from '@tanstack/react-router'
import PhysicalInventoryPage from '@/pages/inventory/PhysicalInventoryPage'

export const Route = createLazyFileRoute('/_app/stock/inventory')({
  component: PhysicalInventoryPage,
})
