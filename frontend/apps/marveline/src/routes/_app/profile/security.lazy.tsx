import { createLazyFileRoute } from '@tanstack/react-router'
import SecurityPage from '@/pages/profile/SecurityPage'

export const Route = createLazyFileRoute('/_app/profile/security')({
  component: SecurityPage,
})
