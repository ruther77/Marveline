import { createLazyFileRoute } from '@tanstack/react-router'
import ReservationCreatePage from '@/pages/events/ReservationCreatePage'

export const Route = createLazyFileRoute('/_app/reservations/new')({
  component: ReservationCreatePage,
})
