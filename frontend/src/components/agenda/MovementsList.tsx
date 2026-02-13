/**
 * Liste des mouvements (vue jour/semaine)
 */
import React from 'react';
import { format, isSameDay, addDays } from 'date-fns';
import { fr } from 'date-fns/locale';
import { AgendaItem } from '../../types/inventory';
import { TruckIcon, PackageIcon, MapPinIcon, PhoneIcon, MailIcon } from 'lucide-react';

interface MovementsListProps {
  events: AgendaItem[];
  viewMode: 'day' | 'week';
  currentDate: Date;
}

const MovementsList: React.FC<MovementsListProps> = ({ events, viewMode, currentDate }) => {
  // Obtenir le badge de statut
  const getStatusBadge = (status: string) => {
    const config = {
      pending: { label: 'En attente', class: 'bg-yellow-100 text-yellow-800' },
      confirmed: { label: 'Confirmé', class: 'bg-blue-100 text-blue-800' },
      in_progress: { label: 'En cours', class: 'bg-purple-100 text-purple-800' },
      completed: { label: 'Terminé', class: 'bg-green-100 text-green-800' },
      cancelled: { label: 'Annulé', class: 'bg-red-100 text-red-800' },
      scheduled: { label: 'Programmé', class: 'bg-blue-100 text-blue-800' },
      in_transit: { label: 'En transit', class: 'bg-purple-100 text-purple-800' },
      late: { label: 'En retard', class: 'bg-red-100 text-red-800' },
    };
    const { label, class: className } = config[status as keyof typeof config] || config.pending;
    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-full ${className}`}>
        {label}
      </span>
    );
  };

  // Obtenir le badge de type d'événement
  const getEventTypeBadge = (type: string) => {
    const config = {
      wedding: { label: 'Mariage', icon: '💒' },
      baptism: { label: 'Baptême', icon: '🕊️' },
      birthday: { label: 'Anniversaire', icon: '🎂' },
      seminar: { label: 'Séminaire', icon: '🏢' },
      other: { label: 'Autre', icon: '📅' },
    };
    const { label, icon } = config[type as keyof typeof config] || config.other;
    return (
      <span className="text-sm text-gray-600">
        {icon} {label}
      </span>
    );
  };

  // Générer les jours à afficher
  const getDaysToShow = () => {
    if (viewMode === 'day') {
      return [currentDate];
    } else {
      // Semaine : 7 jours à partir du lundi
      return Array.from({ length: 7 }, (_, i) => addDays(currentDate, i));
    }
  };

  const days = getDaysToShow();

  // Filtrer les événements par jour
  const getEventsForDay = (day: Date): AgendaItem[] => {
    return events.filter(event => {
      const rentalStart = new Date(event.rental_start_date);
      const rentalEnd = new Date(event.rental_end_date);
      return day >= rentalStart && day <= rentalEnd;
    });
  };

  return (
    <div className="space-y-6">
      {days.map(day => {
        const dayEvents = getEventsForDay(day);
        const isToday = isSameDay(day, new Date());

        return (
          <div key={day.toISOString()} className="bg-white rounded-lg shadow overflow-hidden">
            {/* En-tête du jour */}
            <div className={`px-6 py-3 border-b ${isToday ? 'bg-indigo-50 border-indigo-200' : 'bg-gray-50 border-gray-200'}`}>
              <h3 className={`text-lg font-semibold ${isToday ? 'text-indigo-900' : 'text-gray-900'}`}>
                {format(day, 'EEEE d MMMM yyyy', { locale: fr })}
                {isToday && (
                  <span className="ml-2 px-2 py-1 text-xs font-medium bg-indigo-600 text-white rounded-full">
                    Aujourd'hui
                  </span>
                )}
              </h3>
            </div>

            {/* Liste des événements */}
            <div className="divide-y divide-gray-200">
              {dayEvents.length === 0 ? (
                <div className="px-6 py-8 text-center text-gray-500">
                  Aucun événement prévu ce jour
                </div>
              ) : (
                dayEvents.map(event => (
                  <div key={event.event_id} className="px-6 py-4 hover:bg-gray-50">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        {/* Informations client */}
                        <div className="flex items-center space-x-3 mb-2">
                          <h4 className="text-lg font-semibold text-gray-900">
                            {event.customer_name}
                          </h4>
                          {getEventTypeBadge(event.event_type)}
                          {getStatusBadge(event.status)}
                        </div>

                        {/* Dates de location */}
                        <div className="text-sm text-gray-600 mb-3">
                          📅 Du {format(new Date(event.rental_start_date), 'd MMM', { locale: fr })} au{' '}
                          {format(new Date(event.rental_end_date), 'd MMM yyyy', { locale: fr })}
                        </div>

                        {/* Mouvements */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {/* Départ/Arrivée */}
                          {event.departure && (
                            <div className="flex items-start space-x-3 p-3 bg-green-50 rounded-lg border border-green-200">
                              <TruckIcon className="h-5 w-5 text-green-600 mt-0.5" />
                              <div className="flex-1">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-sm font-medium text-green-900">
                                    Arrivée chez le client
                                  </span>
                                  {getStatusBadge(event.departure.status)}
                                </div>
                                <div className="text-xs text-green-700">
                                  📅 {format(new Date(event.departure.scheduled_date), 'HH:mm', { locale: fr })}
                                  {event.departure.delivery_method && (
                                    <span className="ml-2">
                                      • {event.departure.delivery_method === 'delivery' ? '🚚 Livraison' :
                                         event.departure.delivery_method === 'pickup' ? '🏢 Retrait' : '📦 Expédition'}
                                    </span>
                                  )}
                                </div>
                                {event.departure.items_count > 0 && (
                                  <div className="text-xs text-green-700 mt-1">
                                    📦 {event.departure.items_count} article(s)
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Retour */}
                          {event.return_movement && (
                            <div className="flex items-start space-x-3 p-3 bg-orange-50 rounded-lg border border-orange-200">
                              <PackageIcon className="h-5 w-5 text-orange-600 mt-0.5" />
                              <div className="flex-1">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-sm font-medium text-orange-900">
                                    Retour en stock
                                  </span>
                                  {getStatusBadge(event.return_movement.status)}
                                </div>
                                <div className="text-xs text-orange-700">
                                  📅 {format(new Date(event.return_movement.scheduled_date), 'HH:mm', { locale: fr })}
                                  {event.return_movement.delivery_method && (
                                    <span className="ml-2">
                                      • {event.return_movement.delivery_method === 'delivery' ? '🚚 Collecte' :
                                         event.return_movement.delivery_method === 'pickup' ? '🏢 Dépôt' : '📦 Retour'}
                                    </span>
                                  )}
                                </div>
                                {event.return_movement.items_count > 0 && (
                                  <div className="text-xs text-orange-700 mt-1">
                                    📦 {event.return_movement.items_count} article(s)
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="ml-4 flex-shrink-0">
                        <button className="px-3 py-1 text-sm font-medium text-indigo-600 hover:text-indigo-800">
                          Détails
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default MovementsList;
