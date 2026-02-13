/**
 * Carte d'événement optimisée pour mobile iOS
 */
import React from 'react';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';
import { AgendaItem } from '../../types/inventory';
import { TruckIcon, PackageIcon, MapPinIcon, PhoneIcon, MailIcon, Clock } from 'lucide-react';

interface MobileEventCardProps {
  event: AgendaItem;
}

const MobileEventCard: React.FC<MobileEventCardProps> = ({ event }) => {
  // Badge de type d'événement
  const getEventTypeConfig = (type: string) => {
    const config = {
      wedding: { label: 'Mariage', emoji: '💒', color: 'pink' },
      baptism: { label: 'Baptême', emoji: '🕊️', color: 'blue' },
      birthday: { label: 'Anniversaire', emoji: '🎂', color: 'purple' },
      seminar: { label: 'Séminaire', emoji: '🏢', color: 'gray' },
      other: { label: 'Autre', emoji: '📅', color: 'indigo' },
    };
    return config[type as keyof typeof config] || config.other;
  };

  // Badge de statut
  const getStatusConfig = (status: string) => {
    const config = {
      pending: { label: 'En attente', color: 'bg-yellow-500' },
      confirmed: { label: 'Confirmé', color: 'bg-blue-500' },
      in_progress: { label: 'En cours', color: 'bg-purple-500' },
      completed: { label: 'Terminé', color: 'bg-green-500' },
      cancelled: { label: 'Annulé', color: 'bg-red-500' },
    };
    return config[status as keyof typeof config] || config.pending;
  };

  const eventType = getEventTypeConfig(event.event_type);
  const statusConfig = getStatusConfig(event.status);

  return (
    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden active:scale-98 transition-transform">
      {/* En-tête avec couleur */}
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <div className="flex items-center space-x-2 mb-1">
              <span className="text-2xl">{eventType.emoji}</span>
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                {eventType.label}
              </span>
            </div>
            <h3 className="text-lg font-bold text-gray-900 leading-tight">
              {event.customer_name}
            </h3>
          </div>
          <div className={`w-3 h-3 rounded-full ${statusConfig.color}`}></div>
        </div>

        {/* Date de l'événement */}
        <div className="flex items-center space-x-2 text-sm text-gray-600">
          <Clock className="h-4 w-4" />
          <span>
            {format(new Date(event.rental_start_date), 'd MMM', { locale: fr })} -{' '}
            {format(new Date(event.rental_end_date), 'd MMM yyyy', { locale: fr })}
          </span>
        </div>
      </div>

      {/* Mouvements */}
      <div className="p-4 space-y-3">
        {/* Arrivée */}
        {event.departure && (
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-2xl p-3 border border-green-100">
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                <TruckIcon className="h-5 w-5 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-semibold text-green-900">
                    Arrivée chez le client
                  </span>
                  <span className="text-xs px-2 py-1 bg-green-200 text-green-800 rounded-full font-medium">
                    {event.departure.status === 'scheduled' ? 'Programmé' :
                     event.departure.status === 'in_transit' ? 'En transit' :
                     event.departure.status === 'completed' ? 'Livré' :
                     event.departure.status === 'late' ? 'En retard' : 'Annulé'}
                  </span>
                </div>
                <div className="text-xs text-green-700 font-medium">
                  {format(new Date(event.departure.scheduled_date), 'HH:mm', { locale: fr })}
                </div>
                {event.departure.delivery_method && (
                  <div className="text-xs text-green-600 mt-1">
                    {event.departure.delivery_method === 'delivery' ? '🚚 Livraison' :
                     event.departure.delivery_method === 'pickup' ? '🏢 Retrait' : '📦 Expédition'}
                  </div>
                )}
                {event.departure.items_count > 0 && (
                  <div className="text-xs text-green-600 mt-1">
                    📦 {event.departure.items_count} article{event.departure.items_count > 1 ? 's' : ''}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Retour */}
        {event.return_movement && (
          <div className="bg-gradient-to-r from-orange-50 to-amber-50 rounded-2xl p-3 border border-orange-100">
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 w-10 h-10 bg-orange-500 rounded-full flex items-center justify-center">
                <PackageIcon className="h-5 w-5 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-semibold text-orange-900">
                    Retour en stock
                  </span>
                  <span className="text-xs px-2 py-1 bg-orange-200 text-orange-800 rounded-full font-medium">
                    {event.return_movement.status === 'scheduled' ? 'Programmé' :
                     event.return_movement.status === 'in_transit' ? 'En cours' :
                     event.return_movement.status === 'completed' ? 'Retourné' :
                     event.return_movement.status === 'late' ? 'En retard' : 'Annulé'}
                  </span>
                </div>
                <div className="text-xs text-orange-700 font-medium">
                  {format(new Date(event.return_movement.scheduled_date), 'HH:mm', { locale: fr })}
                </div>
                {event.return_movement.delivery_method && (
                  <div className="text-xs text-orange-600 mt-1">
                    {event.return_movement.delivery_method === 'delivery' ? '🚚 Collecte' :
                     event.return_movement.delivery_method === 'pickup' ? '🏢 Dépôt' : '📦 Retour'}
                  </div>
                )}
                {event.return_movement.items_count > 0 && (
                  <div className="text-xs text-orange-600 mt-1">
                    📦 {event.return_movement.items_count} article{event.return_movement.items_count > 1 ? 's' : ''}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Pied de carte */}
      <div className="px-4 pb-4">
        <button className="w-full py-3 bg-indigo-600 text-white rounded-2xl font-semibold active:scale-98 transition-transform">
          Voir les détails
        </button>
      </div>
    </div>
  );
};

export default MobileEventCard;
