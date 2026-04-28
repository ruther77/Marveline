import { createFileRoute } from '@tanstack/react-router'
import type { DevisStatus } from '@/types/devis'

export const Route = createFileRoute('/_app/devis/')({
  validateSearch: (search): { page?: number; q?: string; status?: DevisStatus | ''; customer_id?: number } => {
    const rawCustomerId = search.customer_id
    let customerId: number | undefined
    if (typeof rawCustomerId === 'number' && rawCustomerId > 0) {
      customerId = rawCustomerId
    } else if (typeof rawCustomerId === 'string') {
      const n = Number(rawCustomerId)
      if (Number.isFinite(n) && n > 0) customerId = n
    }
    return {
      page:        typeof search.page   === 'number' ? search.page : 1,
      q:           typeof search.q      === 'string' ? search.q    : '',
      status:      typeof search.status === 'string' ? search.status as DevisStatus | '' : '' as DevisStatus | '',
      customer_id: customerId,
    }
  },
})
