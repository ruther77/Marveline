import { createFileRoute } from '@tanstack/react-router'
import PlanningTodayPage from '@/pages/planning/PlanningTodayPage'
import AgendaMobilePage from '@/pages/agenda/AgendaMobilePage'

function TodayRoute() {
  const { view } = Route.useSearch()
  if (view === 'mobile') return <AgendaMobilePage />
  return <PlanningTodayPage />
}

export const Route = createFileRoute('/_app/planning/today')({
  validateSearch: (search: Record<string, unknown>) => ({
    view: search.view as 'mobile' | undefined,
  }),
  component: TodayRoute,
})
