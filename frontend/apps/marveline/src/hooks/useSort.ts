import { useState, useMemo, useCallback } from 'react';

export type SortDirection = 'asc' | 'desc' | null;

export interface SortState<T = string> {
  key: T | null;
  direction: SortDirection;
}

export interface UseSortOptions<T = string> {
  initialKey?: T | null;
  initialDirection?: SortDirection;
  defaultDirection?: 'asc' | 'desc';
}

export interface UseSortResult<T = string> {
  sortKey: T | null;
  sortDirection: SortDirection;
  sort: SortState<T>;
  setSort: (key: T) => void;
  setSortState: (state: SortState<T>) => void;
  clearSort: () => void;
  getSortParams: () => { sort_by?: T; sort_order?: 'asc' | 'desc' };
  isSortedBy: (key: T) => boolean;
  getSortDirection: (key: T) => SortDirection;
}

/**
 * Hook pour gérer le tri
 */
export function useSort<T = string>(
  options: UseSortOptions<T> = {}
): UseSortResult<T> {
  const {
    initialKey = null,
    initialDirection = null,
    defaultDirection = 'asc',
  } = options;

  const [sortState, setSortState] = useState<SortState<T>>({
    key: initialKey,
    direction: initialDirection,
  });

  const setSort = useCallback(
    (key: T) => {
      setSortState((prev) => {
        // Si même clé, toggle direction
        if (prev.key === key) {
          if (prev.direction === 'asc') {
            return { key, direction: 'desc' };
          }
          if (prev.direction === 'desc') {
            // Reset après desc
            return { key: null, direction: null };
          }
        }
        // Nouvelle clé, direction par défaut
        return { key, direction: defaultDirection };
      });
    },
    [defaultDirection]
  );

  const clearSort = useCallback(() => {
    setSortState({ key: null, direction: null });
  }, []);

  const getSortParams = useCallback(() => {
    if (!sortState.key || !sortState.direction) {
      return {};
    }
    return {
      sort_by: sortState.key,
      sort_order: sortState.direction,
    };
  }, [sortState]);

  const isSortedBy = useCallback(
    (key: T) => sortState.key === key,
    [sortState.key]
  );

  const getSortDirection = useCallback(
    (key: T): SortDirection => {
      return sortState.key === key ? sortState.direction : null;
    },
    [sortState]
  );

  return {
    sortKey: sortState.key,
    sortDirection: sortState.direction,
    sort: sortState,
    setSort,
    setSortState,
    clearSort,
    getSortParams,
    isSortedBy,
    getSortDirection,
  };
}

/**
 * Hook pour trier un tableau côté client
 */
export function useClientSort<T extends Record<string, unknown>>(
  data: T[],
  options: UseSortOptions<keyof T> = {}
) {
  const sort = useSort<keyof T>(options);

  const sortedData = useMemo(() => {
    if (!sort.sortKey || !sort.sortDirection) {
      return data;
    }

    return [...data].sort((a, b) => {
      const aVal = a[sort.sortKey!];
      const bVal = b[sort.sortKey!];

      // Handle nulls
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return sort.sortDirection === 'asc' ? 1 : -1;
      if (bVal == null) return sort.sortDirection === 'asc' ? -1 : 1;

      // Compare
      let comparison = 0;
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        comparison = aVal.localeCompare(bVal, 'fr', { sensitivity: 'base' });
      } else if (typeof aVal === 'number' && typeof bVal === 'number') {
        comparison = aVal - bVal;
      } else if (aVal instanceof Date && bVal instanceof Date) {
        comparison = aVal.getTime() - bVal.getTime();
      } else {
        comparison = String(aVal).localeCompare(String(bVal));
      }

      return sort.sortDirection === 'desc' ? -comparison : comparison;
    });
  }, [data, sort.sortKey, sort.sortDirection]);

  return {
    ...sort,
    data: sortedData,
  };
}
