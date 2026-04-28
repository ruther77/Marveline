import { createLazyFileRoute } from '@tanstack/react-router'
import TarificationPage from '@/pages/tarification/TarificationPage'

export const Route = createLazyFileRoute('/_app/finance/pricing')({
  component: TarificationPage,
})
