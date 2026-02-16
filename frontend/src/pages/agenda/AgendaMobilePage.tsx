import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { inventoryApi } from '@/api/inventory'
import { reservationsApi } from '@/api/reservations'
import {
  ChevronLeft,
  ChevronRight,
  Calendar,
  Truck,
  RotateCcw,
  CalendarCheck,
  Loader2,
} from 'lucide-react'
import { cn } from '@/lib/utils'

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

  const { data: agendaData, isLoading: agendaLoading } = useQuery({
    queryKey: ['agenda-mobile', startDate, endDate],
    queryFn: () => inventoryApi.getAgenda(startDate, endDate),
  })

  const { data: reservationsData, isLoading: reservationsLoading } = useQuery({
    queryKey: ['reservations-mobile', startDate, endDate],
    queryFn: () =>
      reservationsApi.getReservations({
        page_size: 200,
        start_date: startDate,
        end_date: endDate,
      }),
  })

  const isLoading = agendaLoading || reservationsLoading

  const eventsByDate = useMemo(() => {
    const map: Record<string, DayEvent[]> = {}

    if (agendaData?.events) {
      for (const item of agendaData.events) {
        if (item.departure?.scheduled_date) {
          const date = item.departure.scheduled_date.split('T')[0]
          if (!map[date]) map[date] = []
          map[date].push({
            id: `dep-${item.event_id}`,
            type: 'departure',
            label: `${item.customer_name}`,
            status: item.departure.status,
          })
        }
        if (item.return_movement?.scheduled_date) {
          const date = item.return_movement.scheduled_date.split('T')[0]
          if (!map[date]) map[date] = []
          map[date].push({
            id: `ret-${item.event_id}`,
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

  const selectedDateObj = new Date(selectedDate + 'T12:00:00')
  const selectedLabel = new Intl.DateTimeFormat('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(selectedDateObj)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Agenda</h1>
        <button onClick={goToToday} className="btn-secondary text-sm flex items-center gap-1.5">
          <Calendar className="w-3.5 h-3.5" />
          Aujourd'hui
        </button>
      </div>

      {/* Week strip */}
      <div className="card p-0 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-2 border-b border-dark-700">
          <button onClick={() => navigateWeek(-1)} className="p-1 hover:bg-dark-700 rounded">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm font-medium">
            {new Intl.DateTimeFormat('fr-FR', { month: 'long', year: 'numeric' }).format(days[0])}
          </span>
          <button onClick={() => navigateWeek(1)} className="p-1 hover:bg-dark-700 rounded">
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
                    !isSelected && !isToday && 'hover:bg-dark-700',
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
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-primary-500" />
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
                  'card flex items-center gap-3 p-3 border',
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
                    <span className="text-xs text-dark-500 capitalize">{ev.status}</span>
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
