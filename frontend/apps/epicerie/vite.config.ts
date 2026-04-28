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
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /\/api\/v1\/(epicerie\/stock|epicerie\/catalogue)/,
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'api-lists', expiration: { maxEntries: 200, maxAgeSeconds: 3600 } },
          },
          {
            urlPattern: /\/api\/v1\/epicerie\/ventes/,
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
        name: 'Épicerie MassaCorp',
        short_name: 'Épicerie',
        description: 'Point de vente, stock et fournisseurs — Épicerie MassaCorp',
        theme_color: '#059669',
        background_color: '#0f172a',
        display: 'standalone',
        scope: '/epicerie/',
        start_url: '/epicerie/',
        icons: [
          { src: '/epicerie/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/epicerie/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/epicerie/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
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
  base: '/epicerie/',
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) return 'vendor-react'
          if (id.includes('@tanstack/react-router') || id.includes('@tanstack/react-query')) return 'vendor-tanstack'
          if (id.includes('lucide-react')) return 'vendor-icons'
          if (id.includes('zustand') || id.includes('date-fns')) return 'vendor-utils'
          if (id.includes('@zxing/browser') || id.includes('@zxing/library')) return 'vendor-qr'
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: parseInt(process.env.PORT || '3003'),
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
