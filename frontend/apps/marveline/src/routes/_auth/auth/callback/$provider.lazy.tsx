import { createLazyFileRoute } from '@tanstack/react-router'
import OAuthCallbackPage from '@/pages/auth/OAuthCallbackPage'

export const Route = createLazyFileRoute('/_auth/auth/callback/$provider')({
  component: OAuthCallbackPage,
})
