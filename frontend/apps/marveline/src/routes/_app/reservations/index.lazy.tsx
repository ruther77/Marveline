import { createLazyFileRoute } from '@tanstack/react-router'
import EventsPage from '@/pages/events/EventsPage'

export const Route = createLazyFileRoute('/_app/reservations/')({
  component: EventsPage,
})
