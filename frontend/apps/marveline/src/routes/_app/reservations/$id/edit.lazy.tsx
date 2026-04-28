import { createLazyFileRoute } from '@tanstack/react-router'
import ReservationEditPage from '@/pages/events/ReservationEditPage'

export const Route = createLazyFileRoute('/_app/reservations/$id/edit')({
  component: ReservationEditPage,
})
