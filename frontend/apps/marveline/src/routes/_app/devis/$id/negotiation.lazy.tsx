import { createLazyFileRoute } from '@tanstack/react-router'
import DevisNegotiationPage from '@/pages/devis/DevisNegotiationPage'

export const Route = createLazyFileRoute('/_app/devis/$id/negotiation')({
  component: DevisNegotiationPage,
})
