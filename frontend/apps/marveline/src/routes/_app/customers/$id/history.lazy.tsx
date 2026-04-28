import { createLazyFileRoute } from '@tanstack/react-router'
import CustomerHistoryPage from '@/pages/customers/CustomerHistoryPage'

export const Route = createLazyFileRoute('/_app/customers/$id/history')({
  component: CustomerHistoryPage,
})
