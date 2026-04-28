import { createLazyFileRoute } from '@tanstack/react-router'
import AuditLogsPage from '@/pages/admin/AuditLogsPage'

export const Route = createLazyFileRoute('/_app/admin/audit-logs')({
  component: AuditLogsPage,
})
