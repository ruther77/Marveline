import { createLazyFileRoute } from '@tanstack/react-router'
import LoginPage from '@/pages/auth/LoginPage'

export const Route = createLazyFileRoute('/_auth/login')({
  component: LoginPage,
})
