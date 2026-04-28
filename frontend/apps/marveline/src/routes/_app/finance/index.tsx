import { createFileRoute } from '@tanstack/react-router'

const CURRENT_YEAR = new Date().getFullYear()

export const Route = createFileRoute('/_app/finance/')({
  validateSearch: (s: Record<string, unknown>): { year?: number } => {
    const y = Number(s.year)
    return { year: y >= 2020 && y <= CURRENT_YEAR + 5 ? y : CURRENT_YEAR }
  },
})
