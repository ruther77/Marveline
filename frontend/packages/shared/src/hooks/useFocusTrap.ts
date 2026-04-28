import { useEffect, useRef, type RefObject } from 'react'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

/**
 * Piège le focus clavier dans un conteneur (modal/dialog).
 *
 * - Focus le premier élément focusable à l'ouverture
 * - Tab/Shift+Tab cyclent dans le conteneur
 * - Escape appelle `onEscape` si fourni
 * - Restaure le focus sur l'élément précédent au démontage
 */
export function useFocusTrap<T extends HTMLElement = HTMLDivElement>(
  onEscape?: () => void,
): RefObject<T> {
  // React 19 : useRef<T>(null) produit RefObject<T | null> qui n'est pas
  // assignable à Ref<T> strict. Cast explicite — le ref n'est lu qu'après
  // mount, donc T garanti par React.
  const containerRef = useRef<T | null>(null) as RefObject<T>
  const previousFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // Sauvegarder le focus actuel pour restauration
    previousFocusRef.current = document.activeElement as HTMLElement | null

    // Focus le premier élément focusable
    const focusables = container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
    if (focusables.length > 0) {
      focusables[0].focus()
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && onEscape) {
        e.preventDefault()
        onEscape()
        return
      }

      if (e.key !== 'Tab') return

      const currentFocusables = container!.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      if (currentFocusables.length === 0) return

      const first = currentFocusables[0]
      const last = currentFocusables[currentFocusables.length - 1]

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      // Restaurer le focus précédent
      previousFocusRef.current?.focus()
    }
  }, [onEscape])

  return containerRef
}
