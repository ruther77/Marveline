import { createLazyFileRoute } from '@tanstack/react-router'
import ApiKeysPage from '@/pages/admin/ApiKeysPage'

export const Route = createLazyFileRoute('/_app/admin/api-keys')({
  component: ApiKeysPage,
})
