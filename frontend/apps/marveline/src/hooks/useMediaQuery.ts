import { useState, useEffect } from 'react';

/**
 * Hook pour écouter les media queries
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.matchMedia(query).matches;
    }
    return false;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia(query);
    setMatches(mediaQuery.matches);

    const handler = (event: MediaQueryListEvent) => {
      setMatches(event.matches);
    };

    // Safari < 14 n'a pas addEventListener sur MediaQueryList
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handler);
    } else {
      mediaQuery.addListener(handler);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', handler);
      } else {
        mediaQuery.removeListener(handler);
      }
    };
  }, [query]);

  return matches;
}

/**
 * Breakpoints Tailwind par défaut
 */
export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
} as const;

export type Breakpoint = keyof typeof breakpoints;

/**
 * Hook pour utiliser les breakpoints Tailwind
 */
export function useBreakpoint(breakpoint: Breakpoint): boolean {
  return useMediaQuery(`(min-width: ${breakpoints[breakpoint]})`);
}

/**
 * Hook pour obtenir le breakpoint actuel
 */
export function useCurrentBreakpoint(): Breakpoint | 'base' {
  const isSm = useMediaQuery(`(min-width: ${breakpoints.sm})`);
  const isMd = useMediaQuery(`(min-width: ${breakpoints.md})`);
  const isLg = useMediaQuery(`(min-width: ${breakpoints.lg})`);
  const isXl = useMediaQuery(`(min-width: ${breakpoints.xl})`);
  const is2xl = useMediaQuery(`(min-width: ${breakpoints['2xl']})`);

  if (is2xl) return '2xl';
  if (isXl) return 'xl';
  if (isLg) return 'lg';
  if (isMd) return 'md';
  if (isSm) return 'sm';
  return 'base';
}

/**
 * Hook pour responsive design
 */
export function useResponsive() {
  const isMobile = useMediaQuery('(max-width: 767px)');
  const isTablet = useMediaQuery('(min-width: 768px) and (max-width: 1023px)');
  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const isLargeDesktop = useMediaQuery('(min-width: 1280px)');

  // Préférence utilisateur pour le mouvement réduit
  const prefersReducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');

  // Préférence thème sombre du système
  const prefersDarkMode = useMediaQuery('(prefers-color-scheme: dark)');

  // Orientation
  const isPortrait = useMediaQuery('(orientation: portrait)');
  const isLandscape = useMediaQuery('(orientation: landscape)');

  // Touch device
  const isTouchDevice = useMediaQuery('(hover: none) and (pointer: coarse)');

  return {
    isMobile,
    isTablet,
    isDesktop,
    isLargeDesktop,
    prefersReducedMotion,
    prefersDarkMode,
    isPortrait,
    isLandscape,
    isTouchDevice,
    breakpoint: useCurrentBreakpoint(),
  };
}
