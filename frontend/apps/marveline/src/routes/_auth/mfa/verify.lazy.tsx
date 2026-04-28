import { createLazyFileRoute } from '@tanstack/react-router'
import MFAVerifyPage from '@/pages/auth/MFAVerifyPage'

export const Route = createLazyFileRoute('/_auth/mfa/verify')({
  component: MFAVerifyPage,
})
