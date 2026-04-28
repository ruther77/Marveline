import { createLazyFileRoute } from '@tanstack/react-router'
import StockAdjustmentsPage from '@/pages/inventory/StockAdjustmentsPage'

export const Route = createLazyFileRoute('/_app/stock/adjustments')({
  component: StockAdjustmentsPage,
})
