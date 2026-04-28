import { createLazyFileRoute } from '@tanstack/react-router'
import MFASetupPage from '@/pages/profile/MFASetupPage'

export const Route = createLazyFileRoute('/_app/profile/mfa')({
  component: MFASetupPage,
})
