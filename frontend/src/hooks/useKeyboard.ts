import { useEffect, useCallback, useRef, useState } from 'react';

type KeyHandler = (event: KeyboardEvent) => void;

export interface KeyboardShortcut {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  meta?: boolean;
  handler: KeyHandler;
  preventDefault?: boolean;
}

/**
 * Hook pour écouter une touche spécifique
 */
export function useKeyPress(
  targetKey: string,
  handler: KeyHandler,
  options: {
    enabled?: boolean;
    ctrl?: boolean;
    shift?: boolean;
    alt?: boolean;
    meta?: boolean;
    preventDefault?: boolean;
  } = {}
): void {
  const {
    enabled = true,
    ctrl = false,
    shift = false,
    alt = false,
    meta = false,
    preventDefault = false,
  } = options;

  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    if (!enabled) return;

    const listener = (event: KeyboardEvent) => {
      const matchesKey = event.key.toLowerCase() === targetKey.toLowerCase();
      const matchesCtrl = ctrl === event.ctrlKey;
      const matchesShift = shift === event.shiftKey;
      const matchesAlt = alt === event.altKey;
      const matchesMeta = meta === event.metaKey;

      if (matchesKey && matchesCtrl && matchesShift && matchesAlt && matchesMeta) {
        if (preventDefault) {
          event.preventDefault();
        }
        handlerRef.current(event);
      }
    };

    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [targetKey, ctrl, shift, alt, meta, preventDefault, enabled]);
}

/**
 * Hook pour gérer plusieurs raccourcis clavier
 */
export function useKeyboardShortcuts(
  shortcuts: KeyboardShortcut[],
  enabled = true
): void {
  const shortcutsRef = useRef(shortcuts);
  shortcutsRef.current = shortcuts;

  useEffect(() => {
    if (!enabled) return;

    const listener = (event: KeyboardEvent) => {
      for (const shortcut of shortcutsRef.current) {
        const matchesKey = event.key.toLowerCase() === shortcut.key.toLowerCase();
        const matchesCtrl = (shortcut.ctrl ?? false) === event.ctrlKey;
        const matchesShift = (shortcut.shift ?? false) === event.shiftKey;
        const matchesAlt = (shortcut.alt ?? false) === event.altKey;
        const matchesMeta = (shortcut.meta ?? false) === event.metaKey;

        if (matchesKey && matchesCtrl && matchesShift && matchesAlt && matchesMeta) {
          if (shortcut.preventDefault !== false) {
            event.preventDefault();
          }
          shortcut.handler(event);
          break;
        }
      }
    };

    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [enabled]);
}

/**
 * Hook pour Escape key (fermer modal, annuler, etc.)
 */
export function useEscapeKey(handler: () => void, enabled = true): void {
  useKeyPress('Escape', handler, { enabled });
}

/**
 * Hook pour Enter key (soumettre, confirmer, etc.)
 */
export function useEnterKey(
  handler: KeyHandler,
  options: { enabled?: boolean; ctrl?: boolean } = {}
): void {
  useKeyPress('Enter', handler, options);
}

/**
 * Hook pour les flèches de navigation
 */
export function useArrowNavigation(
  onUp: () => void,
  onDown: () => void,
  options: {
    enabled?: boolean;
    onLeft?: () => void;
    onRight?: () => void;
    loop?: boolean;
  } = {}
): void {
  const { enabled = true, onLeft, onRight } = options;

  useKeyboardShortcuts(
    [
      { key: 'ArrowUp', handler: onUp },
      { key: 'ArrowDown', handler: onDown },
      ...(onLeft ? [{ key: 'ArrowLeft', handler: onLeft }] : []),
      ...(onRight ? [{ key: 'ArrowRight', handler: onRight }] : []),
    ],
    enabled
  );
}

/**
 * Hook pour navigation dans une liste
 */
export function useListNavigation<T>(
  items: T[],
  options: {
    enabled?: boolean;
    loop?: boolean;
    onSelect?: (item: T, index: number) => void;
  } = {}
) {
  const { enabled = true, loop = true, onSelect } = options;
  const [activeIndex, setActiveIndex] = useState(0);

  const goUp = useCallback(() => {
    setActiveIndex((prev) => {
      if (prev <= 0) {
        return loop ? items.length - 1 : 0;
      }
      return prev - 1;
    });
  }, [items.length, loop]);

  const goDown = useCallback(() => {
    setActiveIndex((prev) => {
      if (prev >= items.length - 1) {
        return loop ? 0 : items.length - 1;
      }
      return prev + 1;
    });
  }, [items.length, loop]);

  const select = useCallback(() => {
    if (items[activeIndex] && onSelect) {
      onSelect(items[activeIndex], activeIndex);
    }
  }, [items, activeIndex, onSelect]);

  useArrowNavigation(goUp, goDown, { enabled });
  useEnterKey(select, { enabled });

  // Reset si la liste change
  useEffect(() => {
    setActiveIndex(0);
  }, [items.length]);

  return {
    activeIndex,
    setActiveIndex,
    activeItem: items[activeIndex],
    goUp,
    goDown,
    select,
  };
}
