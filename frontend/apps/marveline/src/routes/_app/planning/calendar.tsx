import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/planning/calendar')({
  validateSearch: (search): {
    year: number
    month: number
    tab: 'calendar' | 'today'
    date?: string
  } => {
    const now = new Date()
    const rawYear = Number(search.year)
    const rawMonth = Number(search.month)
    return {
      year: rawYear >= 2020 && rawYear <= 2100 ? rawYear : now.getFullYear(),
      month: rawMonth >= 0 && rawMonth <= 11 ? rawMonth : now.getMonth(),
      tab: search.tab === 'today' ? 'today' : 'calendar',
      date: typeof search.date === 'string' ? search.date : undefined,
    }
  },
})
