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

const DAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const MONTHS = [
  'Janvier', 'Fevrier', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Aout', 'Septembre', 'Octobre', 'Novembre', 'Decembre',
]

interface CalendarEvent {
  id: string
  date: string
  type: 'departure' | 'return' | 'reservation'
  label: string
  status: string
}

function getMonthRange(year: number, month: number) {
  const start = new Date(year, month, 1)
  const end = new Date(year, month + 1, 0)
  return {
    startDate: start.toISOString().split('T')[0],
    endDate: end.toISOString().split('T')[0],
  }
}

function getCalendarDays(year: number, month: number) {
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)

  // Day of week: Monday=0 ... Sunday=6
  let startDow = firstDay.getDay() - 1
  if (startDow < 0) startDow = 6

  const days: Array<{ date: string; day: number; inMonth: boolean }> = []

  // Previous month padding
  for (let i = startDow - 1; i >= 0; i--) {
    const d = new Date(year, month, -i)
    days.push({
      date: d.toISOString().split('T')[0],
      day: d.getDate(),
      inMonth: false,
    })
  }

  // Current month
  for (let d = 1; d <= lastDay.getDate(); d++) {
    const date = new Date(year, month, d)
    days.push({
      date: date.toISOString().split('T')[0],
      day: d,
      inMonth: true,
    })
  }

  // Next month padding (fill to complete weeks)
  const remaining = 7 - (days.length % 7)
  if (remaining < 7) {
    for (let i = 1; i <= remaining; i++) {
      const d = new Date(year, month + 1, i)
      days.push({
        date: d.toISOString().split('T')[0],
        day: d.getDate(),
        inMonth: false,
      })
    }
  }

  return days
}

function EventDot({ type }: { type: CalendarEvent['type'] }) {
  return (
    <span
      className={cn(
        'w-2 h-2 rounded-full flex-shrink-0',
        type === 'departure' && 'bg-orange-400',
        type === 'return' && 'bg-blue-400',
        type === 'reservation' && 'bg-green-400',
      )}
    />
  )
}

export default function AgendaPage() {
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth())
  const [selectedDate, setSelectedDate] = useState<string | null>(null)

  const { startDate, endDate } = getMonthRange(year, month)

  const { data: agendaData, isLoading: agendaLoading } = useQuery({
    queryKey: ['agenda', startDate, endDate],
    queryFn: () => inventoryApi.getAgenda(startDate, endDate),
  })

  const { data: reservationsData, isLoading: reservationsLoading } = useQuery({
    queryKey: ['reservations-agenda', startDate, endDate],
    queryFn: () =>
      reservationsApi.getReservations({
        page_size: 200,
        start_date: startDate,
        end_date: endDate,
      }),
  })

  const isLoading = agendaLoading || reservationsLoading

  // Build calendar events from agenda + reservations
  const events = useMemo(() => {
    const result: CalendarEvent[] = []

    // Movements from agenda endpoint
    if (agendaData?.events) {
      for (const item of agendaData.events) {
        if (item.departure?.scheduled_date) {
          const date = item.departure.scheduled_date.split('T')[0]
          result.push({
            id: `dep-${item.event_id}`,
            date,
            type: 'departure',
            label: `Depart: ${item.customer_name}`,
            status: item.departure.status,
          })
        }
        if (item.return_movement?.scheduled_date) {
          const date = item.return_movement.scheduled_date.split('T')[0]
          result.push({
            id: `ret-${item.event_id}`,
            date,
            type: 'return',
            label: `Retour: ${item.customer_name}`,
            status: item.return_movement.status,
          })
        }
      }
    }

    // Reservations (event dates)
    if (reservationsData?.items) {
      for (const res of reservationsData.items) {
        if (res.event_date) {
          result.push({
            id: `res-${res.id}`,
            date: res.event_date.split('T')[0],
            type: 'reservation',
            label: `${res.reference}`,
            status: res.status,
          })
        }
      }
    }

    return result
  }, [agendaData, reservationsData])

  // Group events by date
  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {}
    for (const event of events) {
      if (!map[event.date]) map[event.date] = []
      map[event.date].push(event)
    }
    return map
  }, [events])

  const calendarDays = getCalendarDays(year, month)
  const todayStr = today.toISOString().split('T')[0]

  const navigateMonth = (delta: number) => {
    const d = new Date(year, month + delta, 1)
    setYear(d.getFullYear())
    setMonth(d.getMonth())
    setSelectedDate(null)
  }

  const goToToday = () => {
    setYear(today.getFullYear())
    setMonth(today.getMonth())
    setSelectedDate(todayStr)
  }

  const selectedEvents = selectedDate ? eventsByDate[selectedDate] || [] : []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agenda</h1>
          <p className="text-dark-400 mt-1">
            Reservations et mouvements du mois
          </p>
        </div>
        <button onClick={goToToday} className="btn-secondary flex items-center gap-2">
          <Calendar className="w-4 h-4" />
          Aujourd'hui
        </button>
      </div>

      {/* Legend */}
      <div className="card flex items-center gap-6 flex-wrap">
        <div className="flex items-center gap-2 text-sm">
          <span className="w-3 h-3 rounded-full bg-orange-400" />
          <span className="text-dark-300">Departs</span>
          {agendaData && (
            <span className="text-dark-500">({agendaData.total_departures})</span>
          )}
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="w-3 h-3 rounded-full bg-blue-400" />
          <span className="text-dark-300">Retours</span>
          {agendaData && (
            <span className="text-dark-500">({agendaData.total_returns})</span>
          )}
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="w-3 h-3 rounded-full bg-green-400" />
          <span className="text-dark-300">Reservations</span>
          {reservationsData && (
            <span className="text-dark-500">({reservationsData.total})</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Calendar */}
        <div className="lg:col-span-2 card p-0 overflow-hidden">
          {/* Month navigation */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-dark-700">
            <button
              onClick={() => navigateMonth(-1)}
              className="p-1.5 hover:bg-dark-700 rounded-lg"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <h2 className="text-lg font-semibold">
              {MONTHS[month]} {year}
            </h2>
            <button
              onClick={() => navigateMonth(1)}
              className="p-1.5 hover:bg-dark-700 rounded-lg"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
            </div>
          ) : (
            <div className="p-2">
              {/* Day headers */}
              <div className="grid grid-cols-7 mb-1">
                {DAYS.map((day) => (
                  <div
                    key={day}
                    className="text-center text-xs font-medium text-dark-500 py-2"
                  >
                    {day}
                  </div>
                ))}
              </div>

              {/* Day cells */}
              <div className="grid grid-cols-7">
                {calendarDays.map((cell, idx) => {
                  const dayEvents = eventsByDate[cell.date] || []
                  const isToday = cell.date === todayStr
                  const isSelected = cell.date === selectedDate

                  return (
                    <button
                      key={idx}
                      onClick={() => setSelectedDate(cell.date)}
                      className={cn(
                        'relative p-1.5 min-h-[72px] border border-transparent rounded-lg transition-colors text-left',
                        cell.inMonth ? 'text-dark-200' : 'text-dark-600',
                        isToday && 'border-primary-500/30 bg-primary-500/5',
                        isSelected && 'border-primary-500 bg-primary-500/10',
                        !isSelected && !isToday && cell.inMonth && 'hover:bg-dark-800/50',
                      )}
                    >
                      <span
                        className={cn(
                          'text-sm font-medium',
                          isToday && 'text-primary-400',
                        )}
                      >
                        {cell.day}
                      </span>
                      {dayEvents.length > 0 && (
                        <div className="flex flex-wrap gap-0.5 mt-1">
                          {dayEvents.slice(0, 3).map((ev) => (
                            <EventDot key={ev.id} type={ev.type} />
                          ))}
                          {dayEvents.length > 3 && (
                            <span className="text-[10px] text-dark-400">
                              +{dayEvents.length - 3}
                            </span>
                          )}
                        </div>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Day details panel */}
        <div className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-dark-700">
            <h3 className="font-medium">
              {selectedDate
                ? new Intl.DateTimeFormat('fr-FR', {
                    weekday: 'long',
                    day: 'numeric',
                    month: 'long',
                  }).format(new Date(selectedDate + 'T12:00:00'))
                : 'Selectionnez un jour'}
            </h3>
          </div>

          <div className="p-4 space-y-3 max-h-[500px] overflow-y-auto">
            {!selectedDate ? (
              <p className="text-dark-500 text-sm text-center py-8">
                Cliquez sur un jour du calendrier pour voir les details
              </p>
            ) : selectedEvents.length === 0 ? (
              <p className="text-dark-500 text-sm text-center py-8">
                Aucun evenement ce jour
              </p>
            ) : (
              selectedEvents.map((ev) => (
                <div
                  key={ev.id}
                  className={cn(
                    'flex items-start gap-3 p-3 rounded-lg border',
                    ev.type === 'departure' && 'border-orange-500/20 bg-orange-500/5',
                    ev.type === 'return' && 'border-blue-500/20 bg-blue-500/5',
                    ev.type === 'reservation' && 'border-green-500/20 bg-green-500/5',
                  )}
                >
                  <div className={cn(
                    'p-1.5 rounded-lg',
                    ev.type === 'departure' && 'bg-orange-500/10',
                    ev.type === 'return' && 'bg-blue-500/10',
                    ev.type === 'reservation' && 'bg-green-500/10',
                  )}>
                    {ev.type === 'departure' && <Truck className="w-4 h-4 text-orange-400" />}
                    {ev.type === 'return' && <RotateCcw className="w-4 h-4 text-blue-400" />}
                    {ev.type === 'reservation' && <CalendarCheck className="w-4 h-4 text-green-400" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{ev.label}</p>
                    <p className="text-xs text-dark-400 mt-0.5 capitalize">{ev.status}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
