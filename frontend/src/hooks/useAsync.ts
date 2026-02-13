import { useState, useCallback, useEffect, useRef } from 'react';

export type AsyncStatus = 'idle' | 'pending' | 'success' | 'error';

export interface AsyncState<T> {
  data: T | null;
  error: Error | null;
  status: AsyncStatus;
  isIdle: boolean;
  isPending: boolean;
  isSuccess: boolean;
  isError: boolean;
}

export interface UseAsyncResult<T, Args extends unknown[]> extends AsyncState<T> {
  execute: (...args: Args) => Promise<T | null>;
  reset: () => void;
  setData: (data: T | null) => void;
}

/**
 * Hook pour gérer les opérations asynchrones
 */
export function useAsync<T, Args extends unknown[] = []>(
  asyncFn: (...args: Args) => Promise<T>,
  options: {
    immediate?: boolean;
    onSuccess?: (data: T) => void;
    onError?: (error: Error) => void;
  } = {}
): UseAsyncResult<T, Args> {
  const { immediate = false, onSuccess, onError } = options;

  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    error: null,
    status: 'idle',
    isIdle: true,
    isPending: false,
    isSuccess: false,
    isError: false,
  });

  // Ref pour éviter les updates sur composant démonté
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const execute = useCallback(
    async (...args: Args): Promise<T | null> => {
      setState({
        data: null,
        error: null,
        status: 'pending',
        isIdle: false,
        isPending: true,
        isSuccess: false,
        isError: false,
      });

      try {
        const result = await asyncFn(...args);

        if (mountedRef.current) {
          setState({
            data: result,
            error: null,
            status: 'success',
            isIdle: false,
            isPending: false,
            isSuccess: true,
            isError: false,
          });
          onSuccess?.(result);
        }

        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err));

        if (mountedRef.current) {
          setState({
            data: null,
            error,
            status: 'error',
            isIdle: false,
            isPending: false,
            isSuccess: false,
            isError: true,
          });
          onError?.(error);
        }

        return null;
      }
    },
    [asyncFn, onSuccess, onError]
  );

  const reset = useCallback(() => {
    setState({
      data: null,
      error: null,
      status: 'idle',
      isIdle: true,
      isPending: false,
      isSuccess: false,
      isError: false,
    });
  }, []);

  const setData = useCallback((data: T | null) => {
    setState((prev) => ({ ...prev, data }));
  }, []);

  // Exécution immédiate
  useEffect(() => {
    if (immediate) {
      execute(...([] as unknown as Args));
    }
  }, [immediate]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    ...state,
    execute,
    reset,
    setData,
  };
}

/**
 * Hook pour fetch avec retry automatique
 */
export interface UseAsyncRetryOptions {
  maxRetries?: number;
  retryDelay?: number;
  backoff?: boolean;
}

export function useAsyncRetry<T, Args extends unknown[] = []>(
  asyncFn: (...args: Args) => Promise<T>,
  options: UseAsyncRetryOptions & {
    onSuccess?: (data: T) => void;
    onError?: (error: Error) => void;
  } = {}
) {
  const {
    maxRetries = 3,
    retryDelay = 1000,
    backoff = true,
    onSuccess,
    onError,
  } = options;

  const [retryCount, setRetryCount] = useState(0);

  const wrappedFn = useCallback(
    async (...args: Args): Promise<T> => {
      let lastError: Error | null = null;

      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
          const result = await asyncFn(...args);
          setRetryCount(0);
          return result;
        } catch (err) {
          lastError = err instanceof Error ? err : new Error(String(err));
          setRetryCount(attempt + 1);

          if (attempt < maxRetries) {
            const delay = backoff ? retryDelay * Math.pow(2, attempt) : retryDelay;
            await new Promise((resolve) => setTimeout(resolve, delay));
          }
        }
      }

      throw lastError;
    },
    [asyncFn, maxRetries, retryDelay, backoff]
  );

  const asyncResult = useAsync(wrappedFn, { onSuccess, onError });

  return {
    ...asyncResult,
    retryCount,
  };
}

/**
 * Hook pour polling
 */
export function usePolling<T>(
  asyncFn: () => Promise<T>,
  interval: number,
  options: {
    enabled?: boolean;
    onSuccess?: (data: T) => void;
    onError?: (error: Error) => void;
  } = {}
) {
  const { enabled = true, onSuccess, onError } = options;
  const asyncResult = useAsync(asyncFn, { onSuccess, onError });

  useEffect(() => {
    if (!enabled) return;

    // Exécution initiale
    asyncResult.execute();

    // Polling
    const intervalId = setInterval(() => {
      asyncResult.execute();
    }, interval);

    return () => clearInterval(intervalId);
  }, [enabled, interval]); // eslint-disable-line react-hooks/exhaustive-deps

  return asyncResult;
}
