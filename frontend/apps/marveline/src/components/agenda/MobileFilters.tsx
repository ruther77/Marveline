/**
 * Modal de filtres optimisée pour iOS
 */
import React, { useState } from 'react';
import { X } from 'lucide-react';
// import { EventType } from '../../types/event';
import { MovementType } from '../../types/inventory';

interface FiltersState {
  eventType?: string;
  status?: string;
  movementType?: MovementType;
  search?: string;
}

interface MobileFiltersProps {
  onClose: () => void;
  onApply: (filters: FiltersState) => void;
}

const MobileFilters: React.FC<MobileFiltersProps> = ({ onClose, onApply }) => {
  const [filters, setFilters] = useState<FiltersState>({});

  const updateFilter = (key: keyof FiltersState, value: string | undefined) => {
    setFilters(prev => ({
      ...prev,
      [key]: value || undefined,
    }));
  };

  const clearAll = () => {
    setFilters({});
  };

  const handleApply = () => {
    onApply(filters);
  };

  const hasFilters = Object.values(filters).some(v => v !== undefined && v !== '');

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 animate-fade-in"
        aria-hidden="true"
        onClick={onClose}
      ></div>

      {/* Modal */}
      <div className="fixed inset-x-0 bottom-0 z-50 animate-slide-up">
        <div className="bg-white rounded-t-3xl shadow-2xl max-h-[85vh] overflow-hidden">
          {/* Handle */}
          <div className="flex justify-center pt-4 pb-2">
            <div className="w-12 h-1.5 bg-gray-300 rounded-full"></div>
          </div>

          {/* En-tête */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
            <h2 className="text-xl font-bold text-gray-900">Filtres</h2>
            <button
              onClick={onClose}
              className="p-2 -mr-2 active:scale-95 transition-transform"
            >
              <X className="h-6 w-6 text-gray-400" />
            </button>
          </div>

          {/* Contenu scrollable */}
          <div className="overflow-y-auto max-h-[60vh] px-6 py-4 space-y-6">
            {/* Recherche */}
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Rechercher
              </label>
              <input
                type="text"
                value={filters.search || ''}
                onChange={(e) => updateFilter('search', e.target.value)}
                placeholder="Nom du client, email..."
                className="w-full px-4 py-4 bg-gray-50 border border-gray-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
              />
            </div>

            {/* Type d'événement */}
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-4">
                Type d'événement
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { value: '', label: 'Tous', emoji: '📅' },
                  { value: 'wedding', label: 'Mariage', emoji: '💒' },
                  { value: 'baptism', label: 'Baptême', emoji: '🕊️' },
                  { value: 'birthday', label: 'Anniversaire', emoji: '🎂' },
                  { value: 'seminar', label: 'Séminaire', emoji: '🏢' },
                  { value: 'other', label: 'Autre', emoji: '📋' },
                ].map(type => (
                  <button
                    key={type.value}
                    onClick={() => updateFilter('eventType', type.value as string)}
                    className={`py-4 px-4 rounded-2xl font-medium text-sm transition-all active:scale-95 ${
                      filters.eventType === type.value || (!filters.eventType && type.value === '')
                        ? 'bg-indigo-600 text-white shadow-lg'
                        : 'bg-gray-50 text-gray-700 border border-gray-200'
                    }`}
                  >
                    <div className="flex items-center justify-center space-x-2">
                      <span>{type.emoji}</span>
                      <span>{type.label}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Statut */}
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-4">
                Statut
              </label>
              <div className="space-y-2">
                {[
                  { value: '', label: 'Tous', color: 'gray' },
                  { value: 'pending', label: 'En attente', color: 'yellow' },
                  { value: 'confirmed', label: 'Confirmé', color: 'blue' },
                  { value: 'in_progress', label: 'En cours', color: 'purple' },
                  { value: 'completed', label: 'Terminé', color: 'green' },
                  { value: 'cancelled', label: 'Annulé', color: 'red' },
                ].map(status => (
                  <button
                    key={status.value}
                    onClick={() => updateFilter('status', status.value)}
                    className={`w-full py-4 px-4 rounded-2xl font-medium text-sm transition-all active:scale-98 flex items-center justify-between ${
                      filters.status === status.value || (!filters.status && status.value === '')
                        ? 'bg-indigo-600 text-white shadow-lg'
                        : 'bg-gray-50 text-gray-700 border border-gray-200'
                    }`}
                  >
                    <span>{status.label}</span>
                    <div className={`w-3 h-3 rounded-full ${
                      filters.status === status.value || (!filters.status && status.value === '')
                        ? 'bg-white'
                        : `bg-${status.color}-500`
                    }`}></div>
                  </button>
                ))}
              </div>
            </div>

            {/* Type de mouvement */}
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-4">
                Type de mouvement
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { value: '', label: 'Tous', emoji: '📦' },
                  { value: 'departure', label: 'Arrivées', emoji: '🚚' },
                  { value: 'return', label: 'Retours', emoji: '↩️' },
                ].map(type => (
                  <button
                    key={type.value}
                    onClick={() => updateFilter('movementType', type.value as MovementType)}
                    className={`py-4 px-4 rounded-2xl font-medium text-sm transition-all active:scale-95 ${
                      filters.movementType === type.value || (!filters.movementType && type.value === '')
                        ? 'bg-indigo-600 text-white shadow-lg'
                        : 'bg-gray-50 text-gray-700 border border-gray-200'
                    }`}
                  >
                    <div className="text-center">
                      <div className="text-xl mb-1">{type.emoji}</div>
                      <div className="text-xs">{type.label}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="px-6 py-4 border-t border-gray-100 space-y-2">
            {hasFilters && (
              <button
                onClick={clearAll}
                className="w-full py-4 bg-gray-100 text-gray-700 rounded-2xl font-semibold active:scale-98 transition-transform"
              >
                Réinitialiser
              </button>
            )}
            <button
              onClick={handleApply}
              className="w-full py-4 bg-indigo-600 text-white rounded-2xl font-semibold shadow-lg active:scale-98 transition-transform"
            >
              Appliquer les filtres
            </button>
          </div>

          {/* Safe area */}
          <div className="h-safe-bottom bg-white"></div>
        </div>
      </div>

      <style>{`
        @keyframes fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        @keyframes slide-up {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }

        .animate-fade-in {
          animation: fade-in 0.2s ease-out;
        }

        .animate-slide-up {
          animation: slide-up 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
      `}</style>
    </>
  );
};

export default MobileFilters;
