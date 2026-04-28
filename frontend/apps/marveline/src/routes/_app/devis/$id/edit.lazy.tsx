import { createLazyFileRoute } from '@tanstack/react-router'
import DevisEditPage from '@/pages/devis/DevisEditPage'

export const Route = createLazyFileRoute('/_app/devis/$id/edit')({
  component: DevisEditPage,
})
