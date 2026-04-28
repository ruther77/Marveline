import { createFileRoute } from '@tanstack/react-router'
import type { CustomerType } from '@/types/customer'

export const Route = createFileRoute('/_app/customers/')({
  validateSearch: (search): { q?: string; type?: CustomerType | ''; relances?: boolean; page?: number } => ({
    q:       typeof search.q       === 'string'  ? search.q       : '',
    type:    typeof search.type    === 'string'  ? search.type as CustomerType | '' : '',
    relances: search.relances === true || search.relances === 'true',
    page:    typeof search.page === 'number' ? Math.max(1, Math.floor(search.page)) : 1,
  }),
})
