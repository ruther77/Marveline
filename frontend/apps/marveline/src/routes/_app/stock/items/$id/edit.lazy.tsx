import { createLazyFileRoute } from '@tanstack/react-router'
import StockItemEditPage from '@/pages/inventory/StockItemEditPage'

export const Route = createLazyFileRoute('/_app/stock/items/$id/edit')({
  component: StockItemEditPage,
})
