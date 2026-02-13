/**
 * Page Agenda optimisée pour iOS (iPhone 14/15)
 * Design moderne avec gestures et animations
 */
import React, { useState, useEffect } from 'react';
import { format, addDays, subDays, startOfWeek, endOfWeek } from 'date-fns';
import { fr } from 'date-fns/locale';
import { ChevronLeft, ChevronRight, Calendar, Filter, Search, Plus } from 'lucide-react';
import { AgendaItem } from '../../types/inventory';
import MobileEventCard from '../../components/agenda/MobileEventCard';
import MobileFilters from '../../components/agenda/MobileFilters';

const AgendaMobilePage: React.FC = () => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [events, setEvents] = useState<AgendaItem[]>([]);
  const [showFilters, setShowFilters] = useState(false);
  const [loading, setLoading] = useState(false);

  // Swipe gesture pour changer de jour
  const [touchStart, setTouchStart] = useState<number | null>(null);
  const [touchEnd, setTouchEnd] = useState<number | null>(null);

  const minSwipeDistance = 50;

  const onTouchStart = (e: React.TouchEvent) => {
    setTouchEnd(null);
    setTouchStart(e.targetTouches[0].clientX);
  };

  const onTouchMove = (e: React.TouchEvent) => {
    setTouchEnd(e.targetTouches[0].clientX);
  };

  const onTouchEnd = () => {
    if (!touchStart || !touchEnd) return;

    const distance = touchStart - touchEnd;
    const isLeftSwipe = distance > minSwipeDistance;
    const isRightSwipe = distance < -minSwipeDistance;

    if (isLeftSwipe) {
      setCurrentDate(d => addDays(d, 1));
    }
    if (isRightSwipe) {
      setCurrentDate(d => subDays(d, 1));
    }
  };

  // Charger les événements
  const loadEvents = async () => {
    setLoading(true);
    try {
      // TODO: Remplacer par un vrai appel API
      const response = await fetch(
        `/api/v1/agenda?start=${currentDate.toISOString()}&end=${currentDate.toISOString()}`
      );
      const data = await response.json();
      setEvents(data.events || []);
    } catch (error) {
      console.error('Erreur:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, [currentDate]);

  const isToday = format(currentDate, 'yyyy-MM-dd') === format(new Date(), 'yyyy-MM-dd');

  return (
    <div className="min-h-screen bg-gradient-to-b from-indigo-50 to-white">
      {/* En-tête fixe avec effet glassmorphism */}
      <div className="sticky top-0 z-50 backdrop-blur-xl bg-white/80 border-b border-gray-200/50">
        {/* Barre de navigation */}
        <div className="px-4 pt-safe">
          <div className="flex items-center justify-between h-14">
            <button className="p-2 -ml-2 active:scale-95 transition-transform">
              <Calendar className="h-6 w-6 text-indigo-600" />
            </button>
            <h1 className="text-lg font-semibold text-gray-900">Agenda</h1>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="p-2 -mr-2 active:scale-95 transition-transform"
            >
              <Filter className="h-6 w-6 text-gray-600" />
            </button>
          </div>
        </div>

        {/* Sélecteur de date avec gestures */}
        <div
          className="px-4 pb-4"
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
        >
          <div className="flex items-center justify-between">
            <button
              onClick={() => setCurrentDate(d => subDays(d, 1))}
              className="p-2 active:scale-95 transition-transform"
            >
              <ChevronLeft className="h-5 w-5 text-gray-600" />
            </button>

            <div className="flex-1 text-center">
              <div className="text-2xl font-bold text-gray-900">
                {format(currentDate, 'd')}
              </div>
              <div className="text-sm text-gray-500">
                {format(currentDate, 'EEEE', { locale: fr })}
              </div>
              <div className="text-xs text-gray-400">
                {format(currentDate, 'MMMM yyyy', { locale: fr })}
              </div>
              {isToday && (
                <div className="mt-1">
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-600 text-white">
                    Aujourd'hui
                  </span>
                </div>
              )}
            </div>

            <button
              onClick={() => setCurrentDate(d => addDays(d, 1))}
              className="p-2 active:scale-95 transition-transform"
            >
              <ChevronRight className="h-5 w-5 text-gray-600" />
            </button>
          </div>

          {/* Indicateur de swipe */}
          <div className="mt-2 flex justify-center">
            <div className="w-12 h-1 bg-gray-300 rounded-full"></div>
          </div>
        </div>

        {/* Statistiques rapides */}
        <div className="px-4 pb-4">
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-white rounded-2xl p-3 shadow-sm border border-gray-100">
              <div className="text-2xl font-bold text-indigo-600">{events.length}</div>
              <div className="text-xs text-gray-500 mt-0.5">Événements</div>
            </div>
            <div className="bg-white rounded-2xl p-3 shadow-sm border border-gray-100">
              <div className="text-2xl font-bold text-green-600">
                {events.filter(e => e.departure).length}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">Arrivées</div>
            </div>
            <div className="bg-white rounded-2xl p-3 shadow-sm border border-gray-100">
              <div className="text-2xl font-bold text-orange-600">
                {events.filter(e => e.return_movement).length}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">Retours</div>
            </div>
          </div>
        </div>
      </div>

      {/* Contenu avec pull-to-refresh */}
      <div className="px-4 pt-4 pb-safe space-y-3">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-10 w-10 border-3 border-indigo-600 border-t-transparent"></div>
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
              <Calendar className="h-8 w-8 text-gray-400" />
            </div>
            <p className="text-gray-500 font-medium">Aucun événement</p>
            <p className="text-sm text-gray-400 mt-1">ce jour</p>
          </div>
        ) : (
          events.map(event => (
            <MobileEventCard key={event.event_id} event={event} />
          ))
        )}
      </div>

      {/* Bouton flottant d'ajout */}
      <button className="fixed bottom-8 right-4 w-14 h-14 bg-indigo-600 rounded-full shadow-lg flex items-center justify-center active:scale-95 transition-transform z-40">
        <Plus className="h-6 w-6 text-white" />
      </button>

      {/* Filtres modal */}
      {showFilters && (
        <MobileFilters
          onClose={() => setShowFilters(false)}
          onApply={(filters) => {
            console.log('Filtres appliqués:', filters);
            setShowFilters(false);
          }}
        />
      )}

      {/* Safe area bottom */}
      <div className="h-safe-bottom"></div>
    </div>
  );
};

export default AgendaMobilePage;
