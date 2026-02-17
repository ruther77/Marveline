/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',  // Écouter sur toutes interfaces (requis pour Docker)
    port: 5173,       // Port standard Vite
    strictPort: true, // Fail si port occupé (pas de fallback auto)
    proxy: {
      '/api': {
        // En dev Docker: api container. En local: localhost:8001
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
