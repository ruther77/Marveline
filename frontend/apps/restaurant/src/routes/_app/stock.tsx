import { createFileRoute } from '@tanstack/react-router'
import StockPage from '../../pages/StockPage'
import { requireManager } from '@/lib/routeGuards'

export const Route = createFileRoute('/_app/stock')({
  beforeLoad: requireManager,
  component: StockPage,
})
