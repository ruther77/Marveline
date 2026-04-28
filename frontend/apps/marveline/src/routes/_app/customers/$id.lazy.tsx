import { createLazyFileRoute } from '@tanstack/react-router'
import CustomerDetailPage from '@/pages/customers/CustomerDetailPage'

export const Route = createLazyFileRoute('/_app/customers/$id')({
  component: CustomerDetailPage,
})
