import { createLazyFileRoute } from '@tanstack/react-router'
import EvenementsListPage from '@/pages/evenements/EvenementsListPage'

export const Route = createLazyFileRoute('/_app/evenements/incidents')({
  component: EvenementsListPage,
})
