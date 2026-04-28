import { createLazyFileRoute } from '@tanstack/react-router'
import RelancesPlanifieesPage from '@/pages/relances/RelancesPlanifieesPage'

export const Route = createLazyFileRoute('/_app/customers/relances')({
  component: RelancesPlanifieesPage,
})
