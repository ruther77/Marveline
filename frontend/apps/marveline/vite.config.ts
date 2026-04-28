/// <reference types="vitest" />
import { defineConfig } from 'vite'
import { TanStackRouterVite } from '@tanstack/router-vite-plugin'
import { VitePWA } from 'vite-plugin-pwa'
import react from '@vitejs/plugin-react'
import path from 'path'
import { brandHtmlPlugin, resolveBrand } from './vite-plugins/brand-html'

// Manifest PWA dynamique base sur VITE_BRAND
// Icons : /icons/* reste generique (formes), differentiation par name+theme+start_url
const brand = resolveBrand()
const brandIconDir = '/icons'

export default defineConfig({
  plugins: [
    brandHtmlPlugin(),
    TanStackRouterVite(),
    react(),
    // PWA désactivé en dev — réactiver pour le build prod
    ...(process.env.NODE_ENV === 'production' ? [VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        skipWaiting: true,
        clientsClaim: true,
        cleanupOutdatedCaches: true,
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        navigateFallbackDenylist: [/^\/epicerie/, /^\/restaurant/],
        runtimeCaching: [
          {
            urlPattern: /\/api\/v1\/(products|categories|bundles|customers|dashboard)/,
            handler: 'NetworkFirst',
            options: { cacheName: `api-lists-${brand.code}`, expiration: { maxEntries: 200, maxAgeSeconds: 3600 } },
          },
          {
            urlPattern: /\/api\/v1\/auth/,
            handler: 'NetworkOnly',
          },
          {
            urlPattern: /\/api\/v1\/tenant\/brand/,
            handler: 'NetworkFirst',
            options: { cacheName: `api-brand-${brand.code}`, expiration: { maxEntries: 5, maxAgeSeconds: 300 } },
          },
        ],
      },
      manifest: {
        name: brand.name,
        short_name: brand.shortName,
        description: brand.description,
        theme_color: brand.colors.primary,
        background_color: '#1a1a2e',
        display: 'standalone',
        scope: '/',
        start_url: `/?brand=${brand.code}`,
        id: `/?brand=${brand.code}`,
        icons: [
          { src: `${brandIconDir}/icon-192.png`, sizes: '192x192', type: 'image/png' },
          { src: `${brandIconDir}/icon-512.png`, sizes: '512x512', type: 'image/png' },
          { src: `${brandIconDir}/icon-maskable-512.png`, sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    })] : []),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@shared': path.resolve(__dirname, '../../packages/shared/src'),
    },
  },
  base: process.env.VITE_BASE_PATH || '/',
  build: {
    chunkSizeWarningLimit: 1400,
    rollupOptions: {
      external: ['@sentry/react', 'web-vitals'],
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) return 'vendor-react'
          if (id.includes('@tanstack/react-router') || id.includes('@tanstack/router') || id.includes('@tanstack/react-query')) return 'vendor-tanstack'
          if (id.includes('lucide-react')) return 'vendor-icons'
          if (id.includes('react-hook-form') || id.includes('zod') || id.includes('@hookform')) return 'vendor-forms'
          if (id.includes('zustand') || id.includes('date-fns')) return 'vendor-utils'
          if (id.includes('recharts')) return 'vendor-recharts'
          if (id.includes('@zxing/browser') || id.includes('@zxing/library')) return 'vendor-qr'
          if (id.includes('react-signature-canvas')) return 'vendor-signature'
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: parseInt(process.env.PORT || '3002'),
    strictPort: true,
    allowedHosts: ['.ngrok-free.dev', '.ngrok.io', '.trycloudflare.com'],
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
