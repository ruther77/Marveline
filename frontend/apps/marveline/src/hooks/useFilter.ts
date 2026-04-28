import { useState, useMemo, useCallback } from 'react';

export type FilterValue = string | number | boolean | string[] | null | undefined;

export interface FilterState {
  [key: string]: FilterValue;
}

export interface UseFilterOptions<T extends FilterState = FilterState> {
  initialFilters?: T;
  debounce?: number;
}

export interface UseFilterResult<T extends FilterState = FilterState> {
  filters: T;
  activeFiltersCount: number;
  hasActiveFilters: boolean;
  setFilter: <K extends keyof T>(key: K, value: T[K]) => void;
  setFilters: (filters: Partial<T>) => void;
  removeFilter: (key: keyof T) => void;
  clearFilters: () => void;
  resetFilters: () => void;
  getFilterParams: () => Record<string, string | string[]>;
  isFilterActive: (key: keyof T) => boolean;
}

/**
 * Hook pour gérer les filtres
 */
export function useFilter<T extends FilterState = FilterState>(
  options: UseFilterOptions<T> = {}
): UseFilterResult<T> {
  const { initialFilters = {} as T } = options;

  const [filters, setFiltersState] = useState<T>(initialFilters);

  const activeFiltersCount = useMemo(() => {
    return Object.values(filters).filter((value) => {
      if (value === null || value === undefined || value === '') return false;
      if (Array.isArray(value) && value.length === 0) return false;
      return true;
    }).length;
  }, [filters]);

  const hasActiveFilters = activeFiltersCount > 0;

  const setFilter = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
    setFiltersState((prev) => ({
      ...prev,
      [key]: value,
    }));
  }, []);

  const setFilters = useCallback((newFilters: Partial<T>) => {
    setFiltersState((prev) => ({
      ...prev,
      ...newFilters,
    }));
  }, []);

  const removeFilter = useCallback((key: keyof T) => {
    setFiltersState((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setFiltersState({} as T);
  }, []);

  const resetFilters = useCallback(() => {
    setFiltersState(initialFilters);
  }, [initialFilters]);

  const getFilterParams = useCallback(() => {
    const params: Record<string, string | string[]> = {};

    Object.entries(filters).forEach(([key, value]) => {
      if (value === null || value === undefined || value === '') return;
      if (Array.isArray(value)) {
        if (value.length > 0) {
          params[key] = value;
        }
      } else if (typeof value === 'boolean') {
        params[key] = value.toString();
      } else {
        params[key] = String(value);
      }
    });

    return params;
  }, [filters]);

  const isFilterActive = useCallback(
    (key: keyof T) => {
      const value = filters[key];
      if (value === null || value === undefined || value === '') return false;
      if (Array.isArray(value) && value.length === 0) return false;
      return true;
    },
    [filters]
  );

  return {
    filters,
    activeFiltersCount,
    hasActiveFilters,
    setFilter,
    setFilters,
    removeFilter,
    clearFilters,
    resetFilters,
    getFilterParams,
    isFilterActive,
  };
}

/**
 * Hook pour filtrer un tableau côté client
 */
export function useClientFilter<T extends Record<string, unknown>>(
  data: T[],
  filterFn: (item: T, filters: FilterState) => boolean,
  options: UseFilterOptions = {}
) {
  const filter = useFilter(options);

  const filteredData = useMemo(() => {
    if (!filter.hasActiveFilters) {
      return data;
    }
    return data.filter((item) => filterFn(item, filter.filters));
  }, [data, filter.filters, filter.hasActiveFilters, filterFn]);

  return {
    ...filter,
    data: filteredData,
    allData: data,
  };
}

/**
 * Utilitaires de filtrage prédéfinis
 */
export const filterUtils = {
  // Filtre texte (contient)
  textContains: (value: unknown, search: string): boolean => {
    if (!search) return true;
    if (value == null) return false;
    return String(value).toLowerCase().includes(search.toLowerCase());
  },

  // Filtre égalité exacte
  equals: (value: unknown, target: unknown): boolean => {
    if (target === null || target === undefined || target === '') return true;
    return value === target;
  },

  // Filtre dans une liste
  inList: (value: unknown, list: unknown[]): boolean => {
    if (!list || list.length === 0) return true;
    return list.includes(value);
  },

  // Filtre plage numérique
  inRange: (value: number, min?: number, max?: number): boolean => {
    if (min !== undefined && value < min) return false;
    if (max !== undefined && value > max) return false;
    return true;
  },

  // Filtre date
  dateInRange: (
    value: Date | string,
    startDate?: Date | string,
    endDate?: Date | string
  ): boolean => {
    const date = new Date(value);
    if (startDate && date < new Date(startDate)) return false;
    if (endDate && date > new Date(endDate)) return false;
    return true;
  },
};
