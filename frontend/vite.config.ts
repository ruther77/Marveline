/// <reference types="vitest" />
import { defineConfig } from 'vite'
import { TanStackRouterVite } from '@tanstack/router-vite-plugin'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [TanStackRouterVite(), react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src-legacy'),
    },
  },
  build: {
    chunkSizeWarningLimit: 1400,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // React core
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) {
            return 'vendor-react'
          }
          // TanStack Router + Query
          if (id.includes('@tanstack/react-router') || id.includes('@tanstack/router') || id.includes('@tanstack/react-query')) {
            return 'vendor-tanstack'
          }
          // Icons
          if (id.includes('lucide-react')) {
            return 'vendor-icons'
          }
          // Forms + validation
          if (id.includes('react-hook-form') || id.includes('zod') || id.includes('@hookform')) {
            return 'vendor-forms'
          }
          // State + misc
          if (id.includes('zustand') || id.includes('date-fns')) {
            return 'vendor-utils'
          }
          // Heavy libs — code-split pour ne pas grossir le bundle initial
          if (id.includes('recharts')) return 'vendor-recharts'
          if (id.includes('@zxing/browser') || id.includes('@zxing/library')) return 'vendor-qr'
          if (id.includes('react-signature-canvas')) return 'vendor-signature'
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',  // Écouter sur toutes interfaces (requis pour Docker)
    port: 5173,       // Port standard Vite
    strictPort: true, // Fail si port occupé (pas de fallback auto)
    watch: {
      // Exclure routeTree.gen.ts du watcher pour éviter la boucle infinie
      // (TanStackRouterVite le réécrit à chaque détection de changement de routes)
      ignored: ['**/routeTree.gen.ts'],
    },
    proxy: {
      '/api': {
        // En dev Docker: api container. En local: localhost:8001
        target: process.env.DOCKER === 'true' ? 'http://api:8000' : 'http://localhost:8001',
        changeOrigin: true,
      },
      '/uploads': {
        target: process.env.DOCKER === 'true' ? 'http://api:8000' : 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
