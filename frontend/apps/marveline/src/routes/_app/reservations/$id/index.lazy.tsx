import { createLazyFileRoute } from '@tanstack/react-router'
import ReservationRouter from '@/pages/reservations/ReservationRouter'

export const Route = createLazyFileRoute('/_app/reservations/$id/')({
  component: ReservationRouter,
})
