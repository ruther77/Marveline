import { createFileRoute } from '@tanstack/react-router'
export const Route = createFileRoute('/_app/catalogue/bundles/')({
  validateSearch: (s: Record<string, unknown>): { page?: number; search?: string; filter?: string; inactive?: boolean } => ({
    page: Number(s.page) || 1,
    search: String(s.search || ''),
    filter: s.filter ? String(s.filter) : undefined,
    inactive: s.inactive === 'true' || s.inactive === true,
  }),
})
