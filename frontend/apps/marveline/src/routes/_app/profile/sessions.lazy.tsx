import { createLazyFileRoute } from '@tanstack/react-router'
import SessionsPage from '@/pages/admin/SessionsPage'

export const Route = createLazyFileRoute('/_app/profile/sessions')({
  component: SessionsPage,
})
