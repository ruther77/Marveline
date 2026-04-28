import { PageHeader } from '@/components/PageHeader'
import { useState, useMemo } from 'react'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { usePlanningTimeline, useReservationsList, usePlanningToday } from '@/api/queries'
import { ReservationDetailsModal } from '@/pages/events/components'
import { MovementDetailModal } from '@/pages/inventory/components'
import {
  ChevronLeft,
  ChevronRight,
  Calendar,
  Truck,
  RotateCcw,
  CalendarCheck,
  Clock,
  Activity,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
} from 'lucide-react'
import { cn, formatDateWeekday } from '@/lib/utils'
import { PAGE_SIZE_SELECT, RESERVATION_STATUS_LABELS } from '@/lib/constants'
import type { PlanningTodayReservation } from '@/types/planning'

// ─── Helpers ─────────────────────────────────────────────────────────────────

const DAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const MONTHS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

interface CalendarEvent {
  id: string
  date: string
  type: 'departure' | 'return' | 'reservation'
  label: string
  status: string
  reservationId?: number
  movementId?: number
}

function toDateStr(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function getMonthRange(year: number, month: number) {
  return {
    startDate: toDateStr(new Date(year, month, 1)),
    endDate: toDateStr(new Date(year, month + 1, 0)),
  }
}

function getCalendarDays(year: number, month: number) {
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  let startDow = firstDay.getDay() - 1
  if (startDow < 0) startDow = 6
  const days: Array<{ date: string; day: number; inMonth: boolean }> = []
  for (let i = startDow - 1; i >= 0; i--) {
    const d = new Date(year, month, -i)
    days.push({ date: toDateStr(d), day: d.getDate(), inMonth: false })
  }
  for (let d = 1; d <= lastDay.getDate(); d++) {
    days.push({ date: toDateStr(new Date(year, month, d)), day: d, inMonth: true })
  }
  const remaining = 7 - (days.length % 7)
  if (remaining < 7) {
    for (let i = 1; i <= remaining; i++) {
      days.push({ date: toDateStr(new Date(year, month + 1, i)), day: new Date(year, month + 1, i).getDate(), inMonth: false })
    }
  }
  return days
}

// ─── Tab Toggle ──────────────────────────────────────────────────────────────

type TabId = 'calendar' | 'today'

function TabToggle({ active, onChange }: { active: TabId; onChange: (t: TabId) => void }) {
  return (
    <div className="flex card p-1">
      {[
        { id: 'calendar' as TabId, label: 'Calendrier', icon: Calendar },
        { id: 'today' as TabId, label: 'Jour J', icon: Clock },
      ].map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={cn(
            'flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all',
            active === id
              ? 'bg-primary-600 text-white shadow-lg shadow-primary-600/20'
              : 'text-dark-400 hover:text-white',
          )}
        >
          <Icon size={14} />
          {label}
        </button>
      ))}
    </div>
  )
}

// ─── Calendar Event Dot ──────────────────────────────────────────────────────

function EventDot({ type }: { type: CalendarEvent['type'] }) {
  return (
    <span className={cn(
      'w-1.5 h-1.5 rounded-full',
      type === 'departure' && 'bg-orange-400',
      type === 'return' && 'bg-blue-400',
      type === 'reservation' && 'bg-green-400',
    )} />
  )
}

// ─── Day Detail Card ─────────────────────────────────────────────────────────

function DayEventCard({ ev, onClick }: { ev: CalendarEvent; onClick: () => void }) {
  const colors = {
    departure: { bg: 'bg-orange-500/5', border: 'border-orange-500/20', icon: 'bg-orange-500/10', iconColor: 'text-orange-400', badge: 'bg-orange-500/10 text-orange-400' },
    return: { bg: 'bg-blue-500/5', border: 'border-blue-500/20', icon: 'bg-blue-500/10', iconColor: 'text-blue-400', badge: 'bg-blue-500/10 text-blue-400' },
    reservation: { bg: 'bg-green-500/5', border: 'border-green-500/20', icon: 'bg-green-500/10', iconColor: 'text-green-400', badge: 'bg-green-500/10 text-green-400' },
  }[ev.type]
  const IconComp = ev.type === 'departure' ? Truck : ev.type === 'return' ? RotateCcw : CalendarCheck
  const typeLabel = ev.type === 'departure' ? 'Départ' : ev.type === 'return' ? 'Retour' : 'Réservation'

  return (
    <button
      onClick={onClick}
      className={cn('w-full text-left flex items-center gap-3 p-3 rounded-xl border transition-all hover:scale-[1.01]', colors.bg, colors.border)}
    >
      <div className={cn('p-2 rounded-lg', colors.icon)}>
        <IconComp className={cn('w-4 h-4', colors.iconColor)} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{ev.label}</p>
        <p className="text-xs text-dark-500 mt-0.5">{RESERVATION_STATUS_LABELS[ev.status] ?? ev.status}</p>
      </div>
      <span className={cn('text-[10px] px-2 py-0.5 rounded-full font-medium', colors.badge)}>{typeLabel}</span>
    </button>
  )
}

// ─── Today KPI ───────────────────────────────────────────────────────────────

function KpiCard({ label, value, color, border, icon: Icon }: {
  label: string; value: number; color: string; border: string; icon: React.ElementType
}) {
  return (
    <div className={cn('rounded-2xl px-4 py-4 border transition-colors', border)}>
      <div className="flex items-center gap-2 mb-1.5">
        <Icon className={cn('w-3.5 h-3.5', color)} />
        <span className="text-[11px] text-dark-400 font-medium uppercase tracking-wider">{label}</span>
      </div>
      <p className={cn('text-2xl font-bold font-display', color)}>{value}</p>
    </div>
  )
}

// ─── Today Reservation Row ───────────────────────────────────────────────────

const TODAY_STATUS_BADGE: Record<string, string> = {
  confirmed: 'bg-green-500/10 text-green-400 border-green-500/30',
  confirmed_risk: 'bg-red-500/10 text-red-400 border-red-500/30',
  pre_check: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  delivered: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  extended: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
}
const TODAY_STATUS_LABEL: Record<string, string> = {
  confirmed: 'Confirmé', confirmed_risk: 'Risque', pre_check: 'Pré-check',
  delivered: 'Livré', extended: 'Prolongé',
}

function TodayRow({ r }: { r: PlanningTodayReservation }) {
  return (
    <Link
      to="/reservations/$id"
      params={{ id: String(r.id) }}
      className="flex items-center gap-4 px-4 py-3.5 hover:bg-dark-800/40 transition-colors group"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="font-semibold text-sm text-white truncate">{r.customer_name || r.reference}</p>
          <span className={cn(
            'text-[10px] px-2 py-0.5 rounded-full border shrink-0',
            TODAY_STATUS_BADGE[r.status] ?? 'bg-dark-800 text-dark-300 border-dark-600',
          )}>
            {TODAY_STATUS_LABEL[r.status] ?? r.status}
          </span>
        </div>
        <p className="text-xs text-dark-500 mt-0.5">{r.reference}{r.event_name ? ` · ${r.event_name}` : ''}</p>
      </div>
      <ArrowRight className="w-4 h-4 text-dark-600 group-hover:text-dark-300 transition-colors shrink-0" />
    </Link>
  )
}

function TodaySection({ title, icon: Icon, items, color }: {
  title: string; icon: React.ElementType; items: PlanningTodayReservation[]; color: string
}) {
  if (items.length === 0) return null
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 px-1">
        <Icon className={cn('w-3.5 h-3.5', color)} />
        <p className="text-[11px] font-semibold text-dark-400 uppercase tracking-wider">{title}</p>
        <span className="text-xs font-bold text-dark-500 ml-auto">{items.length}</span>
      </div>
      <div className="card p-0 overflow-hidden divide-y divide-dark-700/50">
        {items.map((r) => <TodayRow key={r.id} r={r} />)}
      </div>
    </div>
  )
}

// ─── Skeleton ────────────────────────────────────────────────────────────────

function PlanSkeleton() {
  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-pulse">
      <div className="flex items-center justify-between gap-3">
        <div className="h-7 bg-dark-800 rounded w-40" />
        <div className="h-10 bg-dark-800 rounded-2xl w-56" />
      </div>
      <div className="rounded-2xl border border-dark-200/10 p-4 space-y-4">
        <div className="h-5 bg-dark-800 rounded w-32 mx-auto" />
        <div className="grid grid-cols-7 gap-1">
          {Array.from({ length: 35 }).map((_, i) => (
            <div key={i} className="h-14 bg-dark-800/60 rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function AgendaPage() {
  const today = new Date()
  const todayStr = toDateStr(today)
  const navTo = useNavigate()

  const { year, month, date: urlDate, tab: urlTab } = useSearch({ strict: false }) as {
    year: number; month: number; date?: string; tab?: 'calendar' | 'today'
  }

  const tab: TabId = urlTab ?? 'calendar'
  const selectedDate = urlDate ?? null

  const setTab = (t: TabId) => navTo({ search: (prev: Record<string, unknown>) => ({ ...prev, tab: t === 'calendar' ? undefined : t }) })
  const setYear = (y: number) => navTo({ search: (prev: Record<string, unknown>) => ({ ...prev, year: y }) })
  const setMonth = (m: number) => navTo({ search: (prev: Record<string, unknown>) => ({ ...prev, month: m }) })
  const setSelectedDate = (d: string | null) => navTo({ search: (prev: Record<string, unknown>) => ({ ...prev, date: d || undefined }) })

  const [selectedReservationId, setSelectedReservationId] = useState<number | undefined>()
  const [selectedMovementId, setSelectedMovementId] = useState<number | undefined>()

  const { startDate, endDate } = getMonthRange(year, month)
  const { data: agendaData, isLoading: agendaLoading } = usePlanningTimeline(startDate, endDate)
  const { data: reservationsData, isLoading: resaLoading } = useReservationsList({
    limit: PAGE_SIZE_SELECT, start_date: startDate, end_date: endDate,
  })
  const { data: todayData, isLoading: todayLoading, refetch: refetchToday, isFetching } = usePlanningToday()

  const isLoading = agendaLoading || resaLoading

  const events = useMemo(() => {
    const result: CalendarEvent[] = []
    if (agendaData?.events) {
      for (const item of agendaData.events) {
        if (item.departure?.scheduled_date) {
          result.push({ id: `dep-${item.reservation_id}`, date: item.departure.scheduled_date.split('T')[0], type: 'departure', label: `Départ · ${item.customer_name}`, status: item.departure.status, movementId: item.departure.id })
        }
        if (item.return_movement?.scheduled_date) {
          result.push({ id: `ret-${item.reservation_id}`, date: item.return_movement.scheduled_date.split('T')[0], type: 'return', label: `Retour · ${item.customer_name}`, status: item.return_movement.status, movementId: item.return_movement.id })
        }
      }
    }
    if (reservationsData?.items) {
      for (const res of reservationsData.items) {
        if (res.event_date) {
          result.push({ id: `res-${res.id}`, date: res.event_date.split('T')[0], type: 'reservation', label: res.reference, status: res.status, reservationId: res.id })
        }
      }
    }
    return result
  }, [agendaData, reservationsData])

  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {}
    for (const ev of events) { (map[ev.date] ??= []).push(ev) }
    return map
  }, [events])

  const calendarDays = getCalendarDays(year, month)
  const selectedEvents = selectedDate ? eventsByDate[selectedDate] || [] : []

  const handleEventClick = (ev: CalendarEvent) => {
    if (ev.reservationId) setSelectedReservationId(ev.reservationId)
    else if (ev.movementId) setSelectedMovementId(ev.movementId)
  }

  const navigateMonth = (delta: number) => {
    const d = new Date(year, month + delta, 1)
    setYear(d.getFullYear())
    setMonth(d.getMonth())
    setSelectedDate(null)
  }

  if (isLoading && tab === 'calendar') return <PlanSkeleton />

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <PageHeader title="Planning" />
        <TabToggle active={tab} onChange={setTab} />
      </div>

      {/* ═══ CALENDAR TAB ═══ */}
      {tab === 'calendar' && (
        <>
          {/* Legend */}
          <div className="flex items-center gap-5 text-xs text-dark-400">
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-orange-400" />Départs{agendaData ? ` (${agendaData.total_departures})` : ''}</span>
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-400" />Retours{agendaData ? ` (${agendaData.total_returns})` : ''}</span>
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-green-400" />Réservations{reservationsData ? ` (${reservationsData.total})` : ''}</span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
            {/* Calendar grid */}
            <div className="card p-0 overflow-hidden">
              {/* Month nav */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-dark-200/10">
                <button onClick={() => navigateMonth(-1)} className="p-2 rounded-xl hover:bg-dark-800 transition-colors">
                  <ChevronLeft className="w-5 h-5 text-dark-400" />
                </button>
                <h2 className="text-base font-semibold font-display">{MONTHS[month]} {year}</h2>
                <button onClick={() => navigateMonth(1)} className="p-2 rounded-xl hover:bg-dark-800 transition-colors">
                  <ChevronRight className="w-5 h-5 text-dark-400" />
                </button>
              </div>

              <div className="p-3">
                {/* Day headers */}
                <div className="grid grid-cols-7 mb-1">
                  {DAYS.map((d) => (
                    <div key={d} className="text-center text-[11px] font-medium text-dark-500 py-2 uppercase tracking-wider">{d}</div>
                  ))}
                </div>

                {/* Day cells */}
                <div className="grid grid-cols-7 gap-1">
                  {calendarDays.map((cell, idx) => {
                    const dayEvs = eventsByDate[cell.date] || []
                    const isToday = cell.date === todayStr
                    const isSelected = cell.date === selectedDate
                    return (
                      <button
                        key={idx}
                        onClick={() => setSelectedDate(cell.date)}
                        className={cn(
                          'relative p-2 min-h-[64px] rounded-xl transition-all text-left',
                          cell.inMonth ? 'text-dark-200' : 'text-dark-600',
                          isToday && !isSelected && 'ring-1 ring-primary-500/40 bg-primary-500/5',
                          isSelected && 'ring-2 ring-primary-500 bg-primary-500/10',
                          !isSelected && !isToday && cell.inMonth && 'hover:bg-dark-800/60',
                        )}
                      >
                        <span className={cn(
                          'text-sm font-medium',
                          isToday && 'text-primary-400',
                        )}>
                          {cell.day}
                        </span>
                        {dayEvs.length > 0 && (
                          <div className="flex gap-0.5 mt-1.5">
                            {dayEvs.slice(0, 4).map((ev) => <EventDot key={ev.id} type={ev.type} />)}
                            {dayEvs.length > 4 && <span className="text-[9px] text-dark-500 ml-0.5">+{dayEvs.length - 4}</span>}
                          </div>
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Today shortcut */}
              <div className="px-5 py-3 border-t border-dark-200/10">
                <button
                  onClick={() => { setYear(today.getFullYear()); setMonth(today.getMonth()); setSelectedDate(todayStr) }}
                  className="text-xs text-primary-400 hover:text-primary-300 font-medium flex items-center gap-1"
                >
                  <Calendar size={12} /> Aujourd'hui
                </button>
              </div>
            </div>

            {/* Day detail panel */}
            <div className="card p-0 overflow-hidden self-start">
              <div className="px-5 py-4 border-b border-dark-200/10">
                <h3 className="font-medium text-sm">
                  {selectedDate ? formatDateWeekday(selectedDate) : 'Sélectionnez un jour'}
                </h3>
              </div>
              <div className="p-3 space-y-2 max-h-[460px] overflow-y-auto">
                {!selectedDate ? (
                  <div className="text-center py-10">
                    <Calendar size={32} className="mx-auto text-dark-600 mb-2" />
                    <p className="text-dark-500 text-xs">Cliquez sur un jour</p>
                  </div>
                ) : selectedEvents.length === 0 ? (
                  <div className="text-center py-10">
                    <p className="text-dark-500 text-xs">Aucun événement</p>
                  </div>
                ) : (
                  selectedEvents.map((ev) => (
                    <DayEventCard key={ev.id} ev={ev} onClick={() => handleEventClick(ev)} />
                  ))
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {/* ═══ TODAY TAB ═══ */}
      {tab === 'today' && (
        <>
          {todayLoading ? (
            <div className="space-y-4 animate-pulse">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="rounded-2xl border border-dark-200/10 p-5 space-y-3">
                    <div className="h-3 bg-dark-800 rounded w-16" />
                    <div className="h-8 bg-dark-800 rounded w-10" />
                  </div>
                ))}
              </div>
            </div>
          ) : todayData && (
            <>
              {/* Date + refresh */}
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-dark-400">
                  {new Date(todayData.date).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
                </p>
                <button
                  onClick={() => refetchToday()}
                  disabled={isFetching}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-xl border border-dark-200/10 text-dark-400 hover:text-white hover:border-dark-500 transition-colors"
                >
                  <RefreshCw size={11} className={isFetching ? 'animate-spin' : ''} />
                  Actualiser
                </button>
              </div>

              {/* KPIs */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <KpiCard label="Départs" value={todayData.total_departures} color="text-blue-400" border="border-blue-500/20 bg-blue-500/5" icon={Truck} />
                <KpiCard label="Retours" value={todayData.total_returns} color="text-green-400" border="border-green-500/20 bg-green-500/5" icon={RotateCcw} />
                <KpiCard label="En cours" value={todayData.total_active} color="text-amber-400" border="border-amber-500/20 bg-amber-500/5" icon={Activity} />
                <KpiCard label="Retards" value={todayData.total_overdue} color={todayData.total_overdue > 0 ? 'text-red-400' : 'text-dark-500'} border={todayData.total_overdue > 0 ? 'border-red-500/30 bg-red-500/10' : 'border-dark-200/10'} icon={AlertTriangle} />
              </div>

              {/* Sections */}
              <div className="space-y-5">
                <TodaySection title="Départs" icon={Truck} items={todayData.departures} color="text-blue-400" />
                <TodaySection title="Retours attendus" icon={RotateCcw} items={todayData.returns_today} color="text-green-400" />
                <TodaySection title="En cours" icon={Activity} items={todayData.active} color="text-amber-400" />
                <TodaySection title="Retards" icon={AlertTriangle} items={todayData.overdue} color="text-red-400" />
              </div>

              {todayData.total_departures === 0 && todayData.total_returns === 0 && todayData.total_active === 0 && (
                <div className="rounded-2xl border border-dark-200/10 p-12 text-center">
                  <Clock size={36} className="mx-auto mb-3 text-dark-600" />
                  <p className="text-dark-400 text-sm">Journée calme — aucune opération.</p>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* Modals */}
      <ReservationDetailsModal isOpen={!!selectedReservationId} onClose={() => setSelectedReservationId(undefined)} reservationId={selectedReservationId} />
      <MovementDetailModal isOpen={!!selectedMovementId} onClose={() => setSelectedMovementId(undefined)} movementId={selectedMovementId} />
    </div>
  )
}
