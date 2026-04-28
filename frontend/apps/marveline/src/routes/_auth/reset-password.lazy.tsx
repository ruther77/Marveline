import { createLazyFileRoute } from '@tanstack/react-router'
import ResetPasswordPage from '@/pages/auth/ResetPasswordPage'

export const Route = createLazyFileRoute('/_auth/reset-password')({
  component: ResetPasswordPage,
})
