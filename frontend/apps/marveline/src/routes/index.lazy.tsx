import { createLazyFileRoute } from '@tanstack/react-router'
import AppSelectorPage from '@/pages/landing/AppSelectorPage'

export const Route = createLazyFileRoute('/')({
  component: AppSelectorPage,
})
