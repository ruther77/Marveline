import { createLazyFileRoute } from '@tanstack/react-router'
import DepartureListPage from '@/pages/operations/DepartureListPage'

export const Route = createLazyFileRoute('/_app/operations/departure/')({
  component: DepartureListPage,
})
