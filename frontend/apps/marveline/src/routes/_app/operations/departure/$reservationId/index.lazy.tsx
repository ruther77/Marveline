import { createLazyFileRoute } from '@tanstack/react-router'
import DepartureInventoryPage from '@/pages/operations/DepartureInventoryPage'

export const Route = createLazyFileRoute('/_app/operations/departure/$reservationId/')({
  component: DepartureInventoryPage,
})
