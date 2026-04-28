import { createLazyFileRoute } from '@tanstack/react-router'
import ScanPage from '@/pages/operations/ScanPage'

export const Route = createLazyFileRoute('/_app/operations/scan')({
  component: ScanPage,
})
