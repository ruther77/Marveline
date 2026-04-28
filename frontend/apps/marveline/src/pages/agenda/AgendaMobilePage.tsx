import { PageHeader } from '@/components/PageHeader'
import { useState, useMemo } from 'react'
import { usePlanningTimeline } from '@/api/queries'
import { useReservationsList } from '@/api/queries'
import {
  ChevronLeft,
  ChevronRight,
  Calendar,
  Truck,
  RotateCcw,
  CalendarCheck,
} from 'lucide-react'
import { cn, formatDateWeekday, formatMonthYear } from '@/lib/utils'
import { PAGE_SIZE_SELECT, RESERVATION_STATUS_LABELS } from '@/lib/constants'

interface DayEvent {
  id: string
  type: 'departure' | 'return' | 'reservation'
  label: string
  status: string
}

function getWeekRange(baseDate: Date) {
  const day = baseDate.getDay()
  // Monday = 0 offset
  const mondayOffset = day === 0 ? -6 : 1 - day
  const monday = new Date(baseDate)
  monday.setDate(baseDate.getDate() + mondayOffset)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)

  const days: Date[] = []
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    days.push(d)
  }

  return {
    days,
    startDate: monday.toISOString().split('T')[0],
    endDate: sunday.toISOString().split('T')[0],
  }
}

const DAY_SHORT = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

const TYPE_CONFIG = {
  departure: { icon: Truck, color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20', label: 'Depart' },
  return: { icon: RotateCcw, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20', label: 'Retour' },
  reservation: { icon: CalendarCheck, color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/20', label: 'Reservation' },
} as const

export default function AgendaMobilePage() {
  const today = new Date()
  const todayStr = today.toISOString().split('T')[0]
  const [baseDate, setBaseDate] = useState(today)
  const [selectedDate, setSelectedDate] = useState(todayStr)

  const { days, startDate, endDate } = useMemo(() => getWeekRange(baseDate), [baseDate])

  const { data: agendaData, isLoading: agendaLoading, error: agendaError, refetch: refetchAgenda } = usePlanningTimeline(startDate, endDate)

  const { data: reservationsData, isLoading: reservationsLoading, error: resaError, refetch: refetchResa } = useReservationsList({
    limit: PAGE_SIZE_SELECT,
    start_date: startDate,
    end_date: endDate,
  })

  const isLoading = agendaLoading || reservationsLoading
  const queryError = agendaError || resaError
  const refetchAll = () => { refetchAgenda(); refetchResa() }

  const eventsByDate = useMemo(() => {
    const map: Record<string, DayEvent[]> = {}

    if (agendaData?.events) {
      for (const item of agendaData.events) {
        if (item.departure?.scheduled_date) {
          const date = item.departure.scheduled_date.split('T')[0]
          if (!map[date]) map[date] = []
          map[date].push({
            id: `dep-${item.reservation_id}`,
            type: 'departure',
            label: `${item.customer_name}`,
            status: item.departure.status,
          })
        }
        if (item.return_movement?.scheduled_date) {
          const date = item.return_movement.scheduled_date.split('T')[0]
          if (!map[date]) map[date] = []
          map[date].push({
            id: `ret-${item.reservation_id}`,
            type: 'return',
            label: `${item.customer_name}`,
            status: item.return_movement.status,
          })
        }
      }
    }

    if (reservationsData?.items) {
      for (const res of reservationsData.items) {
        if (res.event_date) {
          const date = res.event_date.split('T')[0]
          if (!map[date]) map[date] = []
          map[date].push({
            id: `res-${res.id}`,
            type: 'reservation',
            label: `${res.reference}`,
            status: res.status,
          })
        }
      }
    }

    return map
  }, [agendaData, reservationsData])

  const navigateWeek = (delta: number) => {
    const d = new Date(baseDate)
    d.setDate(d.getDate() + delta * 7)
    setBaseDate(d)
    // Select Monday of new week
    const newWeek = getWeekRange(d)
    setSelectedDate(newWeek.days[0].toISOString().split('T')[0])
  }

  const goToToday = () => {
    setBaseDate(today)
    setSelectedDate(todayStr)
  }

  const selectedEvents = eventsByDate[selectedDate] || []

  const selectedLabel = formatDateWeekday(selectedDate)

  if (queryError) return (
    <div className="card text-center py-12">
      <p className="text-red-400 mb-4">Erreur lors du chargement de l'agenda.</p>
      <button onClick={() => refetchAll()} className="btn-secondary text-sm">Réessayer</button>
    </div>
  )

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="Agenda" />
        <button onClick={goToToday} className="btn-secondary text-sm flex items-center gap-1.5">
          <Calendar className="w-3.5 h-3.5" />
          Aujourd'hui
        </button>
      </div>

      {/* Week strip */}
      <div className="card p-0 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 border-b border-dark-600">
          <button onClick={() => navigateWeek(-1)} className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-dark-600 rounded">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm font-medium">
            {formatMonthYear(days[0])}
          </span>
          <button onClick={() => navigateWeek(1)} className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-dark-600 rounded">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        <div className="grid grid-cols-7 px-1 py-2">
          {days.map((day, idx) => {
            const dateStr = day.toISOString().split('T')[0]
            const isToday = dateStr === todayStr
            const isSelected = dateStr === selectedDate
            const hasEvents = (eventsByDate[dateStr] || []).length > 0

            return (
              <button
                key={idx}
                onClick={() => setSelectedDate(dateStr)}
                className="flex flex-col items-center gap-1 py-1.5"
              >
                <span className="text-[10px] text-dark-500">{DAY_SHORT[idx]}</span>
                <span
                  className={cn(
                    'w-8 h-8 flex items-center justify-center rounded-full text-sm font-medium transition-colors',
                    isSelected && 'bg-primary-500 text-white',
                    isToday && !isSelected && 'border border-primary-500/50 text-primary-400',
                    !isSelected && !isToday && 'hover:bg-dark-600',
                  )}
                >
                  {day.getDate()}
                </span>
                {hasEvents && (
                  <span className={cn(
                    'w-1.5 h-1.5 rounded-full',
                    isSelected ? 'bg-white' : 'bg-primary-400',
                  )} />
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Selected day label */}
      <h2 className="text-lg font-semibold capitalize">{selectedLabel}</h2>

      {/* Events list */}
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-4 space-y-2">
              <div className="h-3 skel rounded w-40" />
              <div className="h-2 skel rounded w-56" />
            </div>
          ))}
        </div>
      ) : selectedEvents.length === 0 ? (
        <div className="card text-center py-8">
          <Calendar className="w-8 h-8 mx-auto mb-2 text-dark-600" />
          <p className="text-dark-500 text-sm">Aucun evenement ce jour</p>
        </div>
      ) : (
        <div className="space-y-2">
          {selectedEvents.map((ev) => {
            const config = TYPE_CONFIG[ev.type]
            const Icon = config.icon
            return (
              <div
                key={ev.id}
                className={cn(
                  'card flex items-center gap-4 p-4 border',
                  config.border, config.bg,
                )}
              >
                <div className={cn('p-2 rounded-lg', config.bg)}>
                  <Icon className={cn('w-4 h-4', config.color)} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={cn('text-xs font-medium', config.color)}>
                      {config.label}
                    </span>
                    <span className="text-xs text-dark-500">{RESERVATION_STATUS_LABELS[ev.status] ?? ev.status}</span>
                  </div>
                  <p className="text-sm font-medium truncate mt-0.5">{ev.label}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-dark-500 flex-shrink-0" />
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
