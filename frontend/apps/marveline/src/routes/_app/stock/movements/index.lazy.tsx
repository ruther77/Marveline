import { createLazyFileRoute } from '@tanstack/react-router'
import MovementsPage from '@/pages/inventory/MovementsPage'

export const Route = createLazyFileRoute('/_app/stock/movements/')({
  component: MovementsPage,
})
