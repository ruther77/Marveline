import { createLazyFileRoute } from '@tanstack/react-router'
import AgendaPage from '@/pages/agenda/AgendaPage'

export const Route = createLazyFileRoute('/_app/planning/calendar')({
  component: AgendaPage,
})
