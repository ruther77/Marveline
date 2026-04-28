import { createLazyFileRoute } from '@tanstack/react-router'
import ReturnInventoryPage from '@/pages/operations/ReturnInventoryPage'

export const Route = createLazyFileRoute('/_app/operations/return/$reservationId/')({
  component: ReturnInventoryPage,
})
