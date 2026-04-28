import { createLazyFileRoute } from '@tanstack/react-router'
import ReservationView from '@/pages/reservations/ReservationView'

export const Route = createLazyFileRoute('/_app/reservations/$id/$phase')({
  component: ReservationView,
})
