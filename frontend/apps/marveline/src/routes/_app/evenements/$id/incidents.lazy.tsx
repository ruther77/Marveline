import { createLazyFileRoute } from '@tanstack/react-router'
import EvenementDetailPage from '@/pages/evenements/EvenementDetailPage'

export const Route = createLazyFileRoute('/_app/evenements/$id/incidents')({
  component: EvenementDetailPage,
})
