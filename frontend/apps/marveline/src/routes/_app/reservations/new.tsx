import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/reservations/new')({
  beforeLoad: ({ search }) => {
    const params: Record<string, string> = {}
    const raw = (search as { customer_id?: number | string }).customer_id
    if (raw) params.customer_id = String(raw)
    throw redirect({ to: '/devis/new', search: params })
  },
})
