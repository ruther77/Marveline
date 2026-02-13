import { useEffect, useRef, useState, RefObject } from 'react';

type Handler = (event: MouseEvent | TouchEvent) => void;

/**
 * Hook pour détecter les clics en dehors d'un élément
 */
export function useOnClickOutside<T extends HTMLElement = HTMLElement>(
  handler: Handler,
  enabled = true
): RefObject<T> {
  const ref = useRef<T>(null);

  useEffect(() => {
    if (!enabled) return;

    const listener = (event: MouseEvent | TouchEvent) => {
      const el = ref.current;

      // Ne rien faire si le clic est à l'intérieur de l'élément
      if (!el || el.contains(event.target as Node)) {
        return;
      }

      handler(event);
    };

    document.addEventListener('mousedown', listener);
    document.addEventListener('touchstart', listener);

    return () => {
      document.removeEventListener('mousedown', listener);
      document.removeEventListener('touchstart', listener);
    };
  }, [handler, enabled]);

  return ref;
}

/**
 * Version avec plusieurs refs (pour les menus avec trigger)
 */
export function useOnClickOutsideMultiple<T extends HTMLElement = HTMLElement>(
  refs: RefObject<T>[],
  handler: Handler,
  enabled = true
): void {
  useEffect(() => {
    if (!enabled) return;

    const listener = (event: MouseEvent | TouchEvent) => {
      // Vérifier si le clic est en dehors de toutes les refs
      const isOutside = refs.every((ref) => {
        const el = ref.current;
        return !el || !el.contains(event.target as Node);
      });

      if (isOutside) {
        handler(event);
      }
    };

    document.addEventListener('mousedown', listener);
    document.addEventListener('touchstart', listener);

    return () => {
      document.removeEventListener('mousedown', listener);
      document.removeEventListener('touchstart', listener);
    };
  }, [refs, handler, enabled]);
}

/**
 * Hook pour fermer au clic extérieur avec état intégré
 */
export function useClickOutsideState<T extends HTMLElement = HTMLElement>(
  initialState = false
): {
  ref: RefObject<T>;
  isOpen: boolean;
  setIsOpen: (value: boolean) => void;
  open: () => void;
  close: () => void;
  toggle: () => void;
} {
  const [isOpen, setIsOpen] = useState(initialState);

  const close = () => setIsOpen(false);
  const open = () => setIsOpen(true);
  const toggle = () => setIsOpen((prev) => !prev);

  const ref = useOnClickOutside<T>(close, isOpen);

  return { ref, isOpen, setIsOpen, open, close, toggle };
}
