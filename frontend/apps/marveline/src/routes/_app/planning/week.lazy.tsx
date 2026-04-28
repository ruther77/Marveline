import { createLazyFileRoute } from '@tanstack/react-router'
import PlanningWeekPage from '@/pages/planning/PlanningWeekPage'

export const Route = createLazyFileRoute('/_app/planning/week')({
  component: PlanningWeekPage,
})
