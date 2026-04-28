import { createLazyFileRoute } from '@tanstack/react-router'
import ProfilePage from '@/pages/profile/ProfilePage'

export const Route = createLazyFileRoute('/_app/profile/')({
  component: ProfilePage,
})
