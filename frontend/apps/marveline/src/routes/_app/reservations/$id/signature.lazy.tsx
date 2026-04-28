import { createLazyFileRoute } from '@tanstack/react-router'
import SignaturePage from '@/pages/events/SignaturePage'

export const Route = createLazyFileRoute('/_app/reservations/$id/signature')({
  component: SignaturePage,
})
