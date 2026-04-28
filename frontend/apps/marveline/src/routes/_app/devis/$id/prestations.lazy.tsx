import { createLazyFileRoute } from '@tanstack/react-router'
import DevisPrestationsPage from '@/pages/devis/DevisPrestationsPage'

export const Route = createLazyFileRoute('/_app/devis/$id/prestations')({
  component: DevisPrestationsPage,
})
