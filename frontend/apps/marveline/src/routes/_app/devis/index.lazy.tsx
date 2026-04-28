import { createLazyFileRoute } from '@tanstack/react-router'
import DevisListPage from '@/pages/devis/DevisListPage'

export const Route = createLazyFileRoute('/_app/devis/')({
  component: DevisListPage,
})
