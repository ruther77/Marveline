import { createLazyFileRoute } from '@tanstack/react-router'
import PlanningDayPage from '@/pages/planning/PlanningDayPage'

export const Route = createLazyFileRoute('/_app/planning/day')({
  component: PlanningDayPage,
})
