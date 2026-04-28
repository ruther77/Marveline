import { createLazyFileRoute } from '@tanstack/react-router'
import ReturnListPage from '@/pages/operations/ReturnListPage'

export const Route = createLazyFileRoute('/_app/operations/return/')({
  component: ReturnListPage,
})
