import { useState, useMemo, useCallback, useEffect } from 'react';

export interface PaginationState {
  page: number;
  perPage: number;
  total: number;
}

export interface PaginationResult {
  // State
  page: number;
  perPage: number;
  total: number;
  totalPages: number;

  // Computed
  startIndex: number;
  endIndex: number;
  hasNextPage: boolean;
  hasPrevPage: boolean;
  isFirstPage: boolean;
  isLastPage: boolean;

  // Actions
  setPage: (page: number) => void;
  setPerPage: (perPage: number) => void;
  setTotal: (total: number) => void;
  nextPage: () => void;
  prevPage: () => void;
  firstPage: () => void;
  lastPage: () => void;
  reset: () => void;

  // Pour les requêtes API
  paginationParams: {
    page: number;
    per_page: number;
    skip: number;
    limit: number;
  };
}

export interface UsePaginationOptions {
  initialPage?: number;
  initialPerPage?: number;
  initialTotal?: number;
}

/**
 * Hook pour gérer la pagination
 */
export function usePagination(options: UsePaginationOptions = {}): PaginationResult {
  const {
    initialPage = 1,
    initialPerPage = 10,
    initialTotal = 0,
  } = options;

  const [page, setPageState] = useState(initialPage);
  const [perPage, setPerPageState] = useState(initialPerPage);
  const [total, setTotal] = useState(initialTotal);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / perPage)),
    [total, perPage]
  );

  const startIndex = useMemo(
    () => (page - 1) * perPage,
    [page, perPage]
  );

  const endIndex = useMemo(
    () => Math.min(startIndex + perPage, total),
    [startIndex, perPage, total]
  );

  const hasNextPage = page < totalPages;
  const hasPrevPage = page > 1;
  const isFirstPage = page === 1;
  const isLastPage = page === totalPages;

  const setPage = useCallback(
    (newPage: number) => {
      const validPage = Math.max(1, Math.min(newPage, totalPages));
      setPageState(validPage);
    },
    [totalPages]
  );

  const setPerPage = useCallback(
    (newPerPage: number) => {
      setPerPageState(newPerPage);
      // Reset à la page 1 quand on change le nombre par page
      setPageState(1);
    },
    []
  );

  const nextPage = useCallback(() => {
    if (hasNextPage) {
      setPageState((p) => p + 1);
    }
  }, [hasNextPage]);

  const prevPage = useCallback(() => {
    if (hasPrevPage) {
      setPageState((p) => p - 1);
    }
  }, [hasPrevPage]);

  const firstPage = useCallback(() => {
    setPageState(1);
  }, []);

  const lastPage = useCallback(() => {
    setPageState(totalPages);
  }, [totalPages]);

  const reset = useCallback(() => {
    setPageState(initialPage);
    setPerPageState(initialPerPage);
    setTotal(initialTotal);
  }, [initialPage, initialPerPage, initialTotal]);

  const paginationParams = useMemo(
    () => ({
      page,
      per_page: perPage,
      skip: startIndex,
      limit: perPage,
    }),
    [page, perPage, startIndex]
  );

  return {
    // State
    page,
    perPage,
    total,
    totalPages,

    // Computed
    startIndex,
    endIndex,
    hasNextPage,
    hasPrevPage,
    isFirstPage,
    isLastPage,

    // Actions
    setPage,
    setPerPage,
    setTotal,
    nextPage,
    prevPage,
    firstPage,
    lastPage,
    reset,

    // API params
    paginationParams,
  };
}

/**
 * Hook pour paginer un tableau côté client
 */
export function useClientPagination<T>(
  data: T[],
  options: UsePaginationOptions = {}
) {
  const pagination = usePagination({
    ...options,
    initialTotal: data.length,
  });
  const { setTotal } = pagination;

  // Mettre à jour le total quand les données changent
  useEffect(() => {
    setTotal(data.length);
  }, [data.length, setTotal]);

  const paginatedData = useMemo(
    () => data.slice(pagination.startIndex, pagination.endIndex),
    [data, pagination.startIndex, pagination.endIndex]
  );

  return {
    ...pagination,
    data: paginatedData,
    allData: data,
  };
}
