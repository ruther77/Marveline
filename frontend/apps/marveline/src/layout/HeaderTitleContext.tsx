/**
 * Context for passing page title from PageHeader → DashboardLayout header.
 * Enables the large-title → inline-title crossfade pattern.
 */
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

interface HeaderTitleState {
  title: string
  progress: number // 0 = large title fully visible, 1 = fully scrolled out
}

interface HeaderTitleContextValue {
  state: HeaderTitleState
  setTitle: (title: string) => void
  setProgress: (progress: number) => void
}

const defaultState: HeaderTitleState = { title: '', progress: 0 }

const HeaderTitleContext = createContext<HeaderTitleContextValue>({
  state: defaultState,
  setTitle: () => {},
  setProgress: () => {},
})

export function HeaderTitleProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<HeaderTitleState>(defaultState)

  const setTitle = useCallback((title: string) => {
    setState((prev) => (prev.title === title ? prev : { ...prev, title }))
  }, [])

  const setProgress = useCallback((progress: number) => {
    setState((prev) => {
      const clamped = Math.max(0, Math.min(1, progress))
      // Avoid re-renders for tiny changes
      if (Math.abs(prev.progress - clamped) < 0.01) return prev
      return { ...prev, progress: clamped }
    })
  }, [])

  return (
    <HeaderTitleContext.Provider value={{ state, setTitle, setProgress }}>
      {children}
    </HeaderTitleContext.Provider>
  )
}

export function useHeaderTitle() {
  return useContext(HeaderTitleContext)
}
