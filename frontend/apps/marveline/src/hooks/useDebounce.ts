import { useState, useEffect } from 'react'

/**
 * Hook pour debouncer une valeur.
 * Utile pour la recherche en temps réel - évite les appels API excessifs.
 *
 * @param value - Valeur à debouncer
 * @param delay - Délai en ms (défaut: 300ms)
 * @returns Valeur debouncée
 *
 * @example
 * const [search, setSearch] = useState('')
 * const debouncedSearch = useDebounce(search, 300)
 *
 * useEffect(() => {
 *   // Appelé seulement après 300ms d'inactivité
 *   fetchResults(debouncedSearch)
 * }, [debouncedSearch])
 */
export function useDebounce<T>(value: T, delay = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(timer)
    }
  }, [value, delay])

  return debouncedValue
}

export default useDebounce
