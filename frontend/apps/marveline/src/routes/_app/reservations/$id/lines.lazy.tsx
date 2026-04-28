import { createLazyFileRoute } from '@tanstack/react-router'
import ReservationLinesPage from '@/pages/events/ReservationLinesPage'

export const Route = createLazyFileRoute('/_app/reservations/$id/lines')({
  component: ReservationLinesPage,
})
