import { createLazyFileRoute } from '@tanstack/react-router'
import FeatureFlagsPage from '@/pages/admin/FeatureFlagsPage'

export const Route = createLazyFileRoute('/_app/admin/features')({
  component: FeatureFlagsPage,
})
