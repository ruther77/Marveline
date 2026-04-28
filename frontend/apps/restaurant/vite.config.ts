/// <reference types="vitest" />
import { defineConfig } from 'vite'
import { TanStackRouterVite } from '@tanstack/router-vite-plugin'
import { VitePWA } from 'vite-plugin-pwa'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [
    TanStackRouterVite(),
    react(),
    // Redirige "/" → "/restaurant/" en dev pour éviter le NotFoundPage
    // quand le dev server est accédé directement sans le basepath.
    {
      name: 'dev-base-redirect',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url === '/' || req.url === '') {
            res.writeHead(302, { Location: '/restaurant/' })
            res.end()
            return
          }
          next()
        })
      },
    },
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /\/api\/v1\/(restaurant\/tables|restaurant\/variantes-plat)/,
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'api-lists', expiration: { maxEntries: 200, maxAgeSeconds: 3600 } },
          },
          {
            urlPattern: /\/api\/v1\/restaurant\/commandes/,
            handler: 'NetworkFirst',
            options: { cacheName: 'api-realtime', expiration: { maxEntries: 50, maxAgeSeconds: 300 }, networkTimeoutSeconds: 3 },
          },
          {
            urlPattern: /\/api\/v1\/auth/,
            handler: 'NetworkOnly',
          },
        ],
      },
      manifest: {
        name: 'Restaurant MassaCorp',
        short_name: 'Restaurant',
        description: 'Service en salle, cuisine et gestion — Restaurant MassaCorp',
        theme_color: '#d97706',
        background_color: '#1c1917',
        display: 'standalone',
        scope: '/restaurant/',
        start_url: '/restaurant/',
        icons: [
          { src: '/restaurant/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/restaurant/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/restaurant/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@shared': path.resolve(__dirname, '../../packages/shared/src'),
    },
  },
  base: '/restaurant/',
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) return 'vendor-react'
          if (id.includes('@tanstack/react-router') || id.includes('@tanstack/react-query')) return 'vendor-tanstack'
          if (id.includes('lucide-react')) return 'vendor-icons'
          if (id.includes('zustand') || id.includes('date-fns')) return 'vendor-utils'
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: parseInt(process.env.PORT || '3004'),
    allowedHosts: ['.ngrok-free.dev', '.ngrok.io'],
    watch: { ignored: ['**/routeTree.gen.ts'] },
    proxy: {
      '/api': {
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
