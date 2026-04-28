import { createLazyFileRoute } from '@tanstack/react-router'
import DevisChangeRequestPage from '@/pages/devis/DevisChangeRequestPage'

export const Route = createLazyFileRoute('/_app/devis/$id/change-requests')({
  component: DevisChangeRequestPage,
})
