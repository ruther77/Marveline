/**
 * Page principale de l'agenda
 * Affiche les événements, arrivées et retours sur un calendrier
 */
import React, { useState, useEffect } from 'react';
import { format, startOfWeek, endOfWeek, addDays, startOfMonth, endOfMonth, addMonths, subMonths } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Calendar, ChevronLeft, ChevronRight, TruckIcon, PackageIcon, Filter } from 'lucide-react';
import { AgendaView, AgendaItem } from '../../types/inventory';
import { EventType } from '../../types/event';
import AgendaCalendar from '../../components/agenda/AgendaCalendar';
import MovementsList from '../../components/agenda/MovementsList';
import AgendaFilters from '../../components/agenda/AgendaFilters';
import { inventoryApi } from '../../api/inventory';

type ViewMode = 'day' | 'week' | 'month';

interface FiltersState {
  eventType?: EventType;
  status?: string;
  movementType?: 'departure' | 'return';
  search?: string;
}

const AgendaPage: React.FC = () => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [viewMode, setViewMode] = useState<ViewMode>('week');
  const [agendaData, setAgendaData] = useState<AgendaView | null>(null);
  const [filters, setFilters] = useState<FiltersState>({});
  const [showFilters, setShowFilters] = useState(false);
  const [loading, setLoading] = useState(false);

  // Calculer les dates de début et fin selon le mode de vue
  const getDateRange = () => {
    switch (viewMode) {
      case 'day':
        return {
          start: currentDate,
          end: currentDate,
        };
      case 'week':
        return {
          start: startOfWeek(currentDate, { locale: fr, weekStartsOn: 1 }),
          end: endOfWeek(currentDate, { locale: fr, weekStartsOn: 1 }),
        };
      case 'month':
        return {
          start: startOfMonth(currentDate),
          end: endOfMonth(currentDate),
        };
    }
  };

  // Charger les données de l'agenda
  const loadAgendaData = async () => {
    setLoading(true);
    try {
      const { start, end } = getDateRange();
      const data = await inventoryApi.getAgenda(
        start.toISOString(),
        end.toISOString()
      );
      setAgendaData(data);
    } catch (error) {
      console.error('Erreur lors du chargement de l\'agenda:', error);
      setAgendaData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAgendaData();
  }, [currentDate, viewMode, filters]);

  // Navigation
  const goToPrevious = () => {
    switch (viewMode) {
      case 'day':
        setCurrentDate(d => addDays(d, -1));
        break;
      case 'week':
        setCurrentDate(d => addDays(d, -7));
        break;
      case 'month':
        setCurrentDate(d => subMonths(d, 1));
        break;
    }
  };

  const goToNext = () => {
    switch (viewMode) {
      case 'day':
        setCurrentDate(d => addDays(d, 1));
        break;
      case 'week':
        setCurrentDate(d => addDays(d, 7));
        break;
      case 'month':
        setCurrentDate(d => addMonths(d, 1));
        break;
    }
  };

  const goToToday = () => {
    setCurrentDate(new Date());
  };

  // Formater le titre selon le mode
  const getTitle = () => {
    switch (viewMode) {
      case 'day':
        return format(currentDate, 'EEEE d MMMM yyyy', { locale: fr });
      case 'week':
        const { start, end } = getDateRange();
        return `${format(start, 'd MMM', { locale: fr })} - ${format(end, 'd MMM yyyy', { locale: fr })}`;
      case 'month':
        return format(currentDate, 'MMMM yyyy', { locale: fr });
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* En-tête */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Calendar className="h-8 w-8 text-indigo-600" />
              <h1 className="text-2xl font-bold text-gray-900">Agenda</h1>
            </div>

            {/* Navigation */}
            <div className="flex items-center space-x-4">
              <button
                onClick={goToToday}
                className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Aujourd'hui
              </button>

              <div className="flex items-center space-x-2">
                <button
                  onClick={goToPrevious}
                  className="p-2 text-gray-400 hover:text-gray-600"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>

                <span className="text-lg font-semibold text-gray-900 min-w-[250px] text-center">
                  {getTitle()}
                </span>

                <button
                  onClick={goToNext}
                  className="p-2 text-gray-400 hover:text-gray-600"
                >
                  <ChevronRight className="h-5 w-5" />
                </button>
              </div>

              {/* Modes de vue */}
              <div className="flex rounded-md shadow-sm">
                <button
                  onClick={() => setViewMode('day')}
                  className={`px-3 py-2 text-sm font-medium rounded-l-md border ${
                    viewMode === 'day'
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  Jour
                </button>
                <button
                  onClick={() => setViewMode('week')}
                  className={`px-3 py-2 text-sm font-medium border-t border-b ${
                    viewMode === 'week'
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  Semaine
                </button>
                <button
                  onClick={() => setViewMode('month')}
                  className={`px-3 py-2 text-sm font-medium rounded-r-md border ${
                    viewMode === 'month'
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  Mois
                </button>
              </div>

              <button
                onClick={() => setShowFilters(!showFilters)}
                className="p-2 text-gray-400 hover:text-gray-600"
              >
                <Filter className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Filtres */}
          {showFilters && (
            <AgendaFilters filters={filters} onFiltersChange={setFilters} />
          )}
        </div>
      </div>

      {/* Statistiques rapides */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <Calendar className="h-8 w-8 text-indigo-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">Événements</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {agendaData?.events.length || 0}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <TruckIcon className="h-8 w-8 text-green-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">Arrivées prévues</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {agendaData?.total_departures || 0}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <PackageIcon className="h-8 w-8 text-orange-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">Retours prévus</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {agendaData?.total_returns || 0}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Contenu principal */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-8">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
          </div>
        ) : viewMode === 'month' ? (
          <AgendaCalendar
            events={agendaData?.events || []}
            currentMonth={currentDate}
          />
        ) : (
          <MovementsList
            events={agendaData?.events || []}
            viewMode={viewMode}
            currentDate={currentDate}
          />
        )}
      </div>
    </div>
  );
};

export default AgendaPage;
