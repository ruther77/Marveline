import { createLazyFileRoute } from '@tanstack/react-router'
import ClientsRFMPage from '@/pages/customers/ClientsRFMPage'

export const Route = createLazyFileRoute('/_app/customers/rfm')({
  component: ClientsRFMPage,
})
