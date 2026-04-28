/**
 * Hook de navigation clavier pour table éditable.
 *
 * Gère une grille 2D de cellules focusables via une Map de refs.
 * Tab/Shift+Tab : cellule suivante/précédente
 * ArrowDown/ArrowUp : même colonne, ligne suivante/précédente
 * Enter : confirme et passe à la cellule suivante
 */
import { useCallback, useRef } from 'react'

interface CellRef {
  row: number
  col: number
  el: HTMLElement
}

export function useTableKeyboardNav() {
  const cellsRef = useRef<Map<string, CellRef>>(new Map())

  const registerCell = useCallback((row: number, col: number, el: HTMLElement | null) => {
    const key = `${row}:${col}`
    if (el) {
      cellsRef.current.set(key, { row, col, el })
    } else {
      cellsRef.current.delete(key)
    }
  }, [])

  const getSortedCells = useCallback(() => {
    return Array.from(cellsRef.current.values()).sort((a, b) =>
      a.row !== b.row ? a.row - b.row : a.col - b.col,
    )
  }, [])

  const focusCell = useCallback((row: number, col: number) => {
    const cell = cellsRef.current.get(`${row}:${col}`)
    if (cell) {
      cell.el.click() // Trigger edit mode
      cell.el.focus()
      return true
    }
    return false
  }, [])

  const handleCellKeyDown = useCallback((e: React.KeyboardEvent, row: number, col: number) => {
    const cells = getSortedCells()
    const currentIdx = cells.findIndex(c => c.row === row && c.col === col)
    if (currentIdx === -1) return

    if (e.key === 'Tab') {
      e.preventDefault()
      const nextIdx = e.shiftKey ? currentIdx - 1 : currentIdx + 1
      if (nextIdx >= 0 && nextIdx < cells.length) {
        const next = cells[nextIdx]
        focusCell(next.row, next.col)
      }
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      // Même colonne, ligne suivante
      const below = cells.find(c => c.col === col && c.row > row)
      if (below) focusCell(below.row, below.col)
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault()
      // Même colonne, ligne précédente
      const above = [...cells].reverse().find(c => c.col === col && c.row < row)
      if (above) focusCell(above.row, above.col)
    }

    if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey) {
      e.preventDefault()
      // Même colonne, ligne suivante (comme un tableur)
      const below = cells.find(c => c.col === col && c.row > row)
      if (below) {
        setTimeout(() => focusCell(below.row, below.col), 50)
      }
    }
  }, [getSortedCells, focusCell])

  return { registerCell, handleCellKeyDown }
}
