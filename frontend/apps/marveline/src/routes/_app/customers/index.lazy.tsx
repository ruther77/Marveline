import { createLazyFileRoute } from '@tanstack/react-router'
import CustomersPage from '@/pages/customers/CustomersPage'

export const Route = createLazyFileRoute('/_app/customers/')({
  component: CustomersPage,
})
