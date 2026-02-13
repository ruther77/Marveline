/**
 * Vue calendrier mensuel de l'agenda
 */
import React from 'react';
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameDay, isSameMonth, startOfWeek, endOfWeek } from 'date-fns';
import { fr } from 'date-fns/locale';
import { AgendaItem } from '../../types/inventory';
import { TruckIcon, PackageIcon } from 'lucide-react';

interface AgendaCalendarProps {
  events: AgendaItem[];
  currentMonth: Date;
}

const AgendaCalendar: React.FC<AgendaCalendarProps> = ({ events, currentMonth }) => {
  // Obtenir tous les jours du mois avec padding pour la semaine
  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const calendarStart = startOfWeek(monthStart, { locale: fr, weekStartsOn: 1 });
  const calendarEnd = endOfWeek(monthEnd, { locale: fr, weekStartsOn: 1 });

  const days = eachDayOfInterval({ start: calendarStart, end: calendarEnd });

  // Jours de la semaine
  const weekDays = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

  // Obtenir les événements pour un jour donné
  const getEventsForDay = (day: Date): AgendaItem[] => {
    return events.filter(event => {
      const eventDate = new Date(event.event_date);
      const rentalStart = new Date(event.rental_start_date);
      const rentalEnd = new Date(event.rental_end_date);

      return isSameDay(eventDate, day) ||
             isSameDay(rentalStart, day) ||
             isSameDay(rentalEnd, day) ||
             (day >= rentalStart && day <= rentalEnd);
    });
  };

  // Obtenir le badge de statut
  const getStatusBadge = (status: string) => {
    const colors = {
      pending: 'bg-yellow-100 text-yellow-800',
      confirmed: 'bg-blue-100 text-blue-800',
      in_progress: 'bg-purple-100 text-purple-800',
      completed: 'bg-green-100 text-green-800',
      cancelled: 'bg-red-100 text-red-800',
    };
    return colors[status as keyof typeof colors] || colors.pending;
  };

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      {/* En-tête des jours */}
      <div className="grid grid-cols-7 gap-px bg-gray-200">
        {weekDays.map(day => (
          <div
            key={day}
            className="bg-gray-50 py-2 text-center text-sm font-semibold text-gray-700"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Grille du calendrier */}
      <div className="grid grid-cols-7 gap-px bg-gray-200">
        {days.map(day => {
          const dayEvents = getEventsForDay(day);
          const isCurrentMonth = isSameMonth(day, currentMonth);
          const isToday = isSameDay(day, new Date());

          return (
            <div
              key={day.toISOString()}
              className={`bg-white min-h-[120px] p-2 ${
                !isCurrentMonth ? 'bg-gray-50' : ''
              }`}
            >
              {/* Numéro du jour */}
              <div className="flex items-center justify-between mb-1">
                <span
                  className={`text-sm font-medium ${
                    isToday
                      ? 'bg-indigo-600 text-white rounded-full w-6 h-6 flex items-center justify-center'
                      : isCurrentMonth
                      ? 'text-gray-900'
                      : 'text-gray-400'
                  }`}
                >
                  {format(day, 'd')}
                </span>

                {/* Indicateurs de mouvements */}
                {dayEvents.length > 0 && (
                  <div className="flex space-x-1">
                    {dayEvents.some(e => e.departure) && (
                      <TruckIcon className="h-4 w-4 text-green-600" />
                    )}
                    {dayEvents.some(e => e.return_movement) && (
                      <PackageIcon className="h-4 w-4 text-orange-600" />
                    )}
                  </div>
                )}
              </div>

              {/* Événements du jour */}
              <div className="space-y-1">
                {dayEvents.slice(0, 3).map(event => (
                  <div
                    key={event.event_id}
                    className={`text-xs p-1 rounded truncate ${getStatusBadge(event.status)}`}
                    title={event.customer_name}
                  >
                    {event.customer_name}
                  </div>
                ))}
                {dayEvents.length > 3 && (
                  <div className="text-xs text-gray-500 text-center">
                    +{dayEvents.length - 3} plus
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default AgendaCalendar;
