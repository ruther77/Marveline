import { createLazyFileRoute } from '@tanstack/react-router'
import InventoryPage from '@/pages/inventory/InventoryPage'

export const Route = createLazyFileRoute('/_app/stock/items/')({
  component: InventoryPage,
})
