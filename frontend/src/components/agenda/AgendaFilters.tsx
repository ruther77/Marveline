/**
 * Filtres de l'agenda
 */
import React from 'react';
import { X } from 'lucide-react';
import { EventType } from '../../types/event';
import { MovementType } from '../../types/inventory';

interface FiltersProps {
  eventType?: EventType;
  status?: string;
  movementType?: MovementType;
  search?: string;
}

interface AgendaFiltersProps {
  filters: FiltersProps;
  onFiltersChange: (filters: FiltersProps) => void;
}

const AgendaFilters: React.FC<AgendaFiltersProps> = ({ filters, onFiltersChange }) => {
  const updateFilter = (key: keyof FiltersProps, value: string | undefined) => {
    onFiltersChange({
      ...filters,
      [key]: value || undefined,
    });
  };

  const clearFilters = () => {
    onFiltersChange({});
  };

  const hasActiveFilters = Object.values(filters).some(v => v !== undefined && v !== '');

  return (
    <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-900">Filtres</h3>
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-sm text-indigo-600 hover:text-indigo-800 flex items-center"
          >
            <X className="h-4 w-4 mr-1" />
            Réinitialiser
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Recherche */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Rechercher
          </label>
          <input
            type="text"
            value={filters.search || ''}
            onChange={(e) => updateFilter('search', e.target.value)}
            placeholder="Nom, email..."
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        {/* Type d'événement */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Type d'événement
          </label>
          <select
            value={filters.eventType || ''}
            onChange={(e) => updateFilter('eventType', e.target.value as EventType)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Tous</option>
            <option value="wedding">💒 Mariage</option>
            <option value="baptism">🕊️ Baptême</option>
            <option value="birthday">🎂 Anniversaire</option>
            <option value="seminar">🏢 Séminaire</option>
            <option value="other">📅 Autre</option>
          </select>
        </div>

        {/* Statut */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Statut
          </label>
          <select
            value={filters.status || ''}
            onChange={(e) => updateFilter('status', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Tous</option>
            <option value="pending">En attente</option>
            <option value="confirmed">Confirmé</option>
            <option value="in_progress">En cours</option>
            <option value="completed">Terminé</option>
            <option value="cancelled">Annulé</option>
          </select>
        </div>

        {/* Type de mouvement */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Type de mouvement
          </label>
          <select
            value={filters.movementType || ''}
            onChange={(e) => updateFilter('movementType', e.target.value as MovementType)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Tous</option>
            <option value="departure">🚚 Arrivées</option>
            <option value="return">📦 Retours</option>
          </select>
        </div>
      </div>
    </div>
  );
};

export default AgendaFilters;
