import { createLazyFileRoute } from '@tanstack/react-router'
import DevisVersionsPage from '@/pages/devis/DevisVersionsPage'

export const Route = createLazyFileRoute('/_app/devis/$id/versions')({
  component: DevisVersionsPage,
})
