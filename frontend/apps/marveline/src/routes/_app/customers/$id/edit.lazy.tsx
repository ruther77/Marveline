import { createLazyFileRoute } from '@tanstack/react-router'
import CustomerEditPage from '@/pages/customers/CustomerEditPage'

export const Route = createLazyFileRoute('/_app/customers/$id/edit')({
  component: CustomerEditPage,
})
