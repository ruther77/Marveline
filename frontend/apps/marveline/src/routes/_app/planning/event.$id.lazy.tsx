import { createLazyFileRoute } from '@tanstack/react-router'
import PlanningEventPanelPage from '@/pages/planning/PlanningEventPanelPage'

export const Route = createLazyFileRoute('/_app/planning/event/$id')({
  component: PlanningEventPanelPage,
})
