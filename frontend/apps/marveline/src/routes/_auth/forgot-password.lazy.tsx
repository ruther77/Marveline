import { createLazyFileRoute } from '@tanstack/react-router'
import ForgotPasswordPage from '@/pages/auth/ForgotPasswordPage'

export const Route = createLazyFileRoute('/_auth/forgot-password')({
  component: ForgotPasswordPage,
})
