import { createLazyFileRoute } from '@tanstack/react-router'
import StockAlertPage from '@/pages/inventory/StockAlertPage'

export const Route = createLazyFileRoute('/_app/stock/alerts/$id')({
  component: StockAlertPage,
})
