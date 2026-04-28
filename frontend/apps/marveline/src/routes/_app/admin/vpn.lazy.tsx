import { createLazyFileRoute } from '@tanstack/react-router'
import VpnPage from '@/pages/admin/VpnPage'

export const Route = createLazyFileRoute('/_app/admin/vpn')({
  component: VpnPage,
})
