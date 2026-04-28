import { createLazyFileRoute } from '@tanstack/react-router'
import PlanningMonthPage from '@/pages/planning/PlanningMonthPage'

export const Route = createLazyFileRoute('/_app/planning/month')({
  component: PlanningMonthPage,
})
