import { createFileRoute } from '@tanstack/react-router'
export const Route = createFileRoute('/_app/finance/invoices/')({
  validateSearch: (s: Record<string, unknown>): { page?: number; reservation_id?: number } => ({
    page: Number(s.page) || 1,
    ...(s.reservation_id ? { reservation_id: Number(s.reservation_id) } : {}),
  }),
})
