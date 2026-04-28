// vite.config.ts
import { defineConfig } from "file:///app/node_modules/.pnpm/vite@5.4.21_terser@5.46.1/node_modules/vite/dist/node/index.js";
import { TanStackRouterVite } from "file:///app/node_modules/.pnpm/@tanstack+router-vite-plugin@1.166.14_@tanstack+react-router@1.167.5_react-dom@18.3.1_r_f5dac57421479471c96eba16bfd860e5/node_modules/@tanstack/router-vite-plugin/dist/esm/index.js";
import { VitePWA } from "file:///app/node_modules/.pnpm/vite-plugin-pwa@1.2.0_vite@5.4.21_terser@5.46.1__workbox-build@7.4.0_@types+babel__core@7.20.5__workbox-window@7.4.0/node_modules/vite-plugin-pwa/dist/index.js";
import react from "file:///app/node_modules/.pnpm/@vitejs+plugin-react@4.7.0_vite@5.4.21_terser@5.46.1_/node_modules/@vitejs/plugin-react/dist/index.js";
import path from "path";
var __vite_injected_original_dirname = "/app/apps/marveline";
var vite_config_default = defineConfig({
  plugins: [
    TanStackRouterVite(),
    react(),
    // PWA désactivé en dev — réactiver pour le build prod
    ...process.env.NODE_ENV === "production" ? [VitePWA({
      registerType: "autoUpdate",
      workbox: {
        skipWaiting: true,
        clientsClaim: true,
        cleanupOutdatedCaches: true,
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        navigateFallbackDenylist: [/^\/epicerie/, /^\/restaurant/],
        runtimeCaching: [
          {
            urlPattern: /\/api\/v1\/(products|categories|bundles|customers|dashboard)/,
            handler: "NetworkFirst",
            options: { cacheName: "api-lists", expiration: { maxEntries: 200, maxAgeSeconds: 3600 } }
          },
          {
            urlPattern: /\/api\/v1\/auth/,
            handler: "NetworkOnly"
          }
        ]
      },
      manifest: {
        name: "Marveline",
        short_name: "Marveline",
        description: "Location \xE9v\xE9nementielle \u2014 vaisselle, mobilier, d\xE9coration",
        theme_color: "#d940a8",
        background_color: "#1a1a2e",
        display: "standalone",
        scope: "/",
        start_url: "/",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" }
        ]
      }
    })] : []
  ],
  resolve: {
    alias: {
      "@": path.resolve(__vite_injected_original_dirname, "./src"),
      "@shared": path.resolve(__vite_injected_original_dirname, "../../packages/shared/src")
    }
  },
  base: "/",
  build: {
    chunkSizeWarningLimit: 1400,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes("node_modules/react/") || id.includes("node_modules/react-dom/")) return "vendor-react";
          if (id.includes("@tanstack/react-router") || id.includes("@tanstack/router") || id.includes("@tanstack/react-query")) return "vendor-tanstack";
          if (id.includes("lucide-react")) return "vendor-icons";
          if (id.includes("react-hook-form") || id.includes("zod") || id.includes("@hookform")) return "vendor-forms";
          if (id.includes("zustand") || id.includes("date-fns")) return "vendor-utils";
          if (id.includes("recharts")) return "vendor-recharts";
          if (id.includes("@zxing/browser") || id.includes("@zxing/library")) return "vendor-qr";
          if (id.includes("react-signature-canvas")) return "vendor-signature";
        }
      }
    }
  },
  server: {
    host: "0.0.0.0",
    port: parseInt(process.env.PORT || "3002"),
    strictPort: true,
    allowedHosts: [".ngrok-free.dev", ".ngrok.io"],
    watch: { ignored: ["**/routeTree.gen.ts"] },
    proxy: {
      "/api": {
        target: process.env.DOCKER === "true" ? "http://api:8000" : "http://localhost:8001",
        changeOrigin: true
      },
      "/uploads": {
        target: process.env.DOCKER === "true" ? "http://api:8000" : "http://localhost:8001",
        changeOrigin: true
      }
    }
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}"]
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvYXBwL2FwcHMvbWFydmVsaW5lXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ZpbGVuYW1lID0gXCIvYXBwL2FwcHMvbWFydmVsaW5lL3ZpdGUuY29uZmlnLnRzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9hcHAvYXBwcy9tYXJ2ZWxpbmUvdml0ZS5jb25maWcudHNcIjsvLy8gPHJlZmVyZW5jZSB0eXBlcz1cInZpdGVzdFwiIC8+XG5pbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tICd2aXRlJ1xuaW1wb3J0IHsgVGFuU3RhY2tSb3V0ZXJWaXRlIH0gZnJvbSAnQHRhbnN0YWNrL3JvdXRlci12aXRlLXBsdWdpbidcbmltcG9ydCB7IFZpdGVQV0EgfSBmcm9tICd2aXRlLXBsdWdpbi1wd2EnXG5pbXBvcnQgcmVhY3QgZnJvbSAnQHZpdGVqcy9wbHVnaW4tcmVhY3QnXG5pbXBvcnQgcGF0aCBmcm9tICdwYXRoJ1xuXG5leHBvcnQgZGVmYXVsdCBkZWZpbmVDb25maWcoe1xuICBwbHVnaW5zOiBbXG4gICAgVGFuU3RhY2tSb3V0ZXJWaXRlKCksXG4gICAgcmVhY3QoKSxcbiAgICAvLyBQV0EgZFx1MDBFOXNhY3Rpdlx1MDBFOSBlbiBkZXYgXHUyMDE0IHJcdTAwRTlhY3RpdmVyIHBvdXIgbGUgYnVpbGQgcHJvZFxuICAgIC4uLihwcm9jZXNzLmVudi5OT0RFX0VOViA9PT0gJ3Byb2R1Y3Rpb24nID8gW1ZpdGVQV0Eoe1xuICAgICAgcmVnaXN0ZXJUeXBlOiAnYXV0b1VwZGF0ZScsXG4gICAgICB3b3JrYm94OiB7XG4gICAgICAgIHNraXBXYWl0aW5nOiB0cnVlLFxuICAgICAgICBjbGllbnRzQ2xhaW06IHRydWUsXG4gICAgICAgIGNsZWFudXBPdXRkYXRlZENhY2hlczogdHJ1ZSxcbiAgICAgICAgZ2xvYlBhdHRlcm5zOiBbJyoqLyoue2pzLGNzcyxodG1sLGljbyxwbmcsc3ZnLHdvZmYyfSddLFxuICAgICAgICBuYXZpZ2F0ZUZhbGxiYWNrRGVueWxpc3Q6IFsvXlxcL2VwaWNlcmllLywgL15cXC9yZXN0YXVyYW50L10sXG4gICAgICAgIHJ1bnRpbWVDYWNoaW5nOiBbXG4gICAgICAgICAge1xuICAgICAgICAgICAgdXJsUGF0dGVybjogL1xcL2FwaVxcL3YxXFwvKHByb2R1Y3RzfGNhdGVnb3JpZXN8YnVuZGxlc3xjdXN0b21lcnN8ZGFzaGJvYXJkKS8sXG4gICAgICAgICAgICBoYW5kbGVyOiAnTmV0d29ya0ZpcnN0JyxcbiAgICAgICAgICAgIG9wdGlvbnM6IHsgY2FjaGVOYW1lOiAnYXBpLWxpc3RzJywgZXhwaXJhdGlvbjogeyBtYXhFbnRyaWVzOiAyMDAsIG1heEFnZVNlY29uZHM6IDM2MDAgfSB9LFxuICAgICAgICAgIH0sXG4gICAgICAgICAge1xuICAgICAgICAgICAgdXJsUGF0dGVybjogL1xcL2FwaVxcL3YxXFwvYXV0aC8sXG4gICAgICAgICAgICBoYW5kbGVyOiAnTmV0d29ya09ubHknLFxuICAgICAgICAgIH0sXG4gICAgICAgIF0sXG4gICAgICB9LFxuICAgICAgbWFuaWZlc3Q6IHtcbiAgICAgICAgbmFtZTogJ01hcnZlbGluZScsXG4gICAgICAgIHNob3J0X25hbWU6ICdNYXJ2ZWxpbmUnLFxuICAgICAgICBkZXNjcmlwdGlvbjogJ0xvY2F0aW9uIFx1MDBFOXZcdTAwRTluZW1lbnRpZWxsZSBcdTIwMTQgdmFpc3NlbGxlLCBtb2JpbGllciwgZFx1MDBFOWNvcmF0aW9uJyxcbiAgICAgICAgdGhlbWVfY29sb3I6ICcjZDk0MGE4JyxcbiAgICAgICAgYmFja2dyb3VuZF9jb2xvcjogJyMxYTFhMmUnLFxuICAgICAgICBkaXNwbGF5OiAnc3RhbmRhbG9uZScsXG4gICAgICAgIHNjb3BlOiAnLycsXG4gICAgICAgIHN0YXJ0X3VybDogJy8nLFxuICAgICAgICBpY29uczogW1xuICAgICAgICAgIHsgc3JjOiAnL2ljb25zL2ljb24tMTkyLnBuZycsIHNpemVzOiAnMTkyeDE5MicsIHR5cGU6ICdpbWFnZS9wbmcnIH0sXG4gICAgICAgICAgeyBzcmM6ICcvaWNvbnMvaWNvbi01MTIucG5nJywgc2l6ZXM6ICc1MTJ4NTEyJywgdHlwZTogJ2ltYWdlL3BuZycgfSxcbiAgICAgICAgICB7IHNyYzogJy9pY29ucy9pY29uLW1hc2thYmxlLTUxMi5wbmcnLCBzaXplczogJzUxMng1MTInLCB0eXBlOiAnaW1hZ2UvcG5nJywgcHVycG9zZTogJ21hc2thYmxlJyB9LFxuICAgICAgICBdLFxuICAgICAgfSxcbiAgICB9KV0gOiBbXSksXG4gIF0sXG4gIHJlc29sdmU6IHtcbiAgICBhbGlhczoge1xuICAgICAgJ0AnOiBwYXRoLnJlc29sdmUoX19kaXJuYW1lLCAnLi9zcmMnKSxcbiAgICAgICdAc2hhcmVkJzogcGF0aC5yZXNvbHZlKF9fZGlybmFtZSwgJy4uLy4uL3BhY2thZ2VzL3NoYXJlZC9zcmMnKSxcbiAgICB9LFxuICB9LFxuICBiYXNlOiAnLycsXG4gIGJ1aWxkOiB7XG4gICAgY2h1bmtTaXplV2FybmluZ0xpbWl0OiAxNDAwLFxuICAgIHJvbGx1cE9wdGlvbnM6IHtcbiAgICAgIG91dHB1dDoge1xuICAgICAgICBtYW51YWxDaHVua3M6IChpZCkgPT4ge1xuICAgICAgICAgIGlmIChpZC5pbmNsdWRlcygnbm9kZV9tb2R1bGVzL3JlYWN0LycpIHx8IGlkLmluY2x1ZGVzKCdub2RlX21vZHVsZXMvcmVhY3QtZG9tLycpKSByZXR1cm4gJ3ZlbmRvci1yZWFjdCdcbiAgICAgICAgICBpZiAoaWQuaW5jbHVkZXMoJ0B0YW5zdGFjay9yZWFjdC1yb3V0ZXInKSB8fCBpZC5pbmNsdWRlcygnQHRhbnN0YWNrL3JvdXRlcicpIHx8IGlkLmluY2x1ZGVzKCdAdGFuc3RhY2svcmVhY3QtcXVlcnknKSkgcmV0dXJuICd2ZW5kb3ItdGFuc3RhY2snXG4gICAgICAgICAgaWYgKGlkLmluY2x1ZGVzKCdsdWNpZGUtcmVhY3QnKSkgcmV0dXJuICd2ZW5kb3ItaWNvbnMnXG4gICAgICAgICAgaWYgKGlkLmluY2x1ZGVzKCdyZWFjdC1ob29rLWZvcm0nKSB8fCBpZC5pbmNsdWRlcygnem9kJykgfHwgaWQuaW5jbHVkZXMoJ0Bob29rZm9ybScpKSByZXR1cm4gJ3ZlbmRvci1mb3JtcydcbiAgICAgICAgICBpZiAoaWQuaW5jbHVkZXMoJ3p1c3RhbmQnKSB8fCBpZC5pbmNsdWRlcygnZGF0ZS1mbnMnKSkgcmV0dXJuICd2ZW5kb3ItdXRpbHMnXG4gICAgICAgICAgaWYgKGlkLmluY2x1ZGVzKCdyZWNoYXJ0cycpKSByZXR1cm4gJ3ZlbmRvci1yZWNoYXJ0cydcbiAgICAgICAgICBpZiAoaWQuaW5jbHVkZXMoJ0B6eGluZy9icm93c2VyJykgfHwgaWQuaW5jbHVkZXMoJ0B6eGluZy9saWJyYXJ5JykpIHJldHVybiAndmVuZG9yLXFyJ1xuICAgICAgICAgIGlmIChpZC5pbmNsdWRlcygncmVhY3Qtc2lnbmF0dXJlLWNhbnZhcycpKSByZXR1cm4gJ3ZlbmRvci1zaWduYXR1cmUnXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIHNlcnZlcjoge1xuICAgIGhvc3Q6ICcwLjAuMC4wJyxcbiAgICBwb3J0OiBwYXJzZUludChwcm9jZXNzLmVudi5QT1JUIHx8ICczMDAyJyksXG4gICAgc3RyaWN0UG9ydDogdHJ1ZSxcbiAgICBhbGxvd2VkSG9zdHM6IFsnLm5ncm9rLWZyZWUuZGV2JywgJy5uZ3Jvay5pbyddLFxuICAgIHdhdGNoOiB7IGlnbm9yZWQ6IFsnKiovcm91dGVUcmVlLmdlbi50cyddIH0sXG4gICAgcHJveHk6IHtcbiAgICAgICcvYXBpJzoge1xuICAgICAgICB0YXJnZXQ6IHByb2Nlc3MuZW52LkRPQ0tFUiA9PT0gJ3RydWUnID8gJ2h0dHA6Ly9hcGk6ODAwMCcgOiAnaHR0cDovL2xvY2FsaG9zdDo4MDAxJyxcbiAgICAgICAgY2hhbmdlT3JpZ2luOiB0cnVlLFxuICAgICAgfSxcbiAgICAgICcvdXBsb2Fkcyc6IHtcbiAgICAgICAgdGFyZ2V0OiBwcm9jZXNzLmVudi5ET0NLRVIgPT09ICd0cnVlJyA/ICdodHRwOi8vYXBpOjgwMDAnIDogJ2h0dHA6Ly9sb2NhbGhvc3Q6ODAwMScsXG4gICAgICAgIGNoYW5nZU9yaWdpbjogdHJ1ZSxcbiAgICAgIH0sXG4gICAgfSxcbiAgfSxcbiAgdGVzdDoge1xuICAgIGdsb2JhbHM6IHRydWUsXG4gICAgZW52aXJvbm1lbnQ6ICdqc2RvbScsXG4gICAgc2V0dXBGaWxlczogJy4vc3JjL3Rlc3Qvc2V0dXAudHMnLFxuICAgIGNzczogZmFsc2UsXG4gICAgaW5jbHVkZTogWydzcmMvKiovKi57dGVzdCxzcGVjfS57dHMsdHN4fSddLFxuICB9LFxufSlcbiJdLAogICJtYXBwaW5ncyI6ICI7QUFDQSxTQUFTLG9CQUFvQjtBQUM3QixTQUFTLDBCQUEwQjtBQUNuQyxTQUFTLGVBQWU7QUFDeEIsT0FBTyxXQUFXO0FBQ2xCLE9BQU8sVUFBVTtBQUxqQixJQUFNLG1DQUFtQztBQU96QyxJQUFPLHNCQUFRLGFBQWE7QUFBQSxFQUMxQixTQUFTO0FBQUEsSUFDUCxtQkFBbUI7QUFBQSxJQUNuQixNQUFNO0FBQUE7QUFBQSxJQUVOLEdBQUksUUFBUSxJQUFJLGFBQWEsZUFBZSxDQUFDLFFBQVE7QUFBQSxNQUNuRCxjQUFjO0FBQUEsTUFDZCxTQUFTO0FBQUEsUUFDUCxhQUFhO0FBQUEsUUFDYixjQUFjO0FBQUEsUUFDZCx1QkFBdUI7QUFBQSxRQUN2QixjQUFjLENBQUMsc0NBQXNDO0FBQUEsUUFDckQsMEJBQTBCLENBQUMsZUFBZSxlQUFlO0FBQUEsUUFDekQsZ0JBQWdCO0FBQUEsVUFDZDtBQUFBLFlBQ0UsWUFBWTtBQUFBLFlBQ1osU0FBUztBQUFBLFlBQ1QsU0FBUyxFQUFFLFdBQVcsYUFBYSxZQUFZLEVBQUUsWUFBWSxLQUFLLGVBQWUsS0FBSyxFQUFFO0FBQUEs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
