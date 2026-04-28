import { createLazyFileRoute } from '@tanstack/react-router'
import StockItemDetailPage from '@/pages/inventory/StockItemDetailPage'

export const Route = createLazyFileRoute('/_app/stock/items/$id/')({
  component: StockItemDetailPage,
})
