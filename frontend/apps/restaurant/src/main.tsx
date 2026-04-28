import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import { routeTree } from './routeTree.gen'
import '@/api' // bootstrap massacorpAuth avant tout
import '@shared/styles/index.css'
import './app.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

// Thème initial — restaurant
;(() => {
  try {
    const stored = localStorage.getItem('restaurant-ui')
    const parsed = stored ? JSON.parse(stored) : null
    const theme: string = parsed?.state?.theme ?? 'dark'
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    document.documentElement.dataset.theme = theme === 'system' ? (systemDark ? 'dark' : 'light') : theme
  } catch {
    document.documentElement.dataset.theme = 'dark'
  }
})()

const router = createRouter({
  routeTree,
  basepath: '/restaurant',
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
)
