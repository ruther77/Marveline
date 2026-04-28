import { createLazyFileRoute } from '@tanstack/react-router'
import DevisCreatePage from '@/pages/devis/DevisCreatePage'

export const Route = createLazyFileRoute('/_app/devis/new')({
  component: DevisCreatePage,
})
