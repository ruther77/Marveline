import { createLazyFileRoute } from '@tanstack/react-router'
import EventIdLayout from '@/pages/events/EventIdLayout'

export const Route = createLazyFileRoute('/_app/reservations/$id')({
  component: EventIdLayout,
})
