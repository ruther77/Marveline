// vite.config.ts
import { defineConfig } from "file:///app/node_modules/.pnpm/vite@5.4.21/node_modules/vite/dist/node/index.js";
import { TanStackRouterVite } from "file:///app/node_modules/.pnpm/@tanstack+router-vite-plugin@1.166.9_@tanstack+react-router@1.167.0_react-dom@18.3.1_re_5ca7d75fa607ff91698f097c7a27ea4d/node_modules/@tanstack/router-vite-plugin/dist/esm/index.js";
import react from "file:///app/node_modules/.pnpm/@vitejs+plugin-react@4.7.0_vite@5.4.21/node_modules/@vitejs/plugin-react/dist/index.js";
import path from "path";
var __vite_injected_original_dirname = "/app/apps/epicerie";
var vite_config_default = defineConfig({
  plugins: [TanStackRouterVite(), react()],
  resolve: {
    alias: {
      "@": path.resolve(__vite_injected_original_dirname, "./src"),
      "@shared": path.resolve(__vite_injected_original_dirname, "../../packages/shared/src")
    }
  },
  base: "/epicerie/",
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes("node_modules/react/") || id.includes("node_modules/react-dom/")) return "vendor-react";
          if (id.includes("@tanstack/react-router") || id.includes("@tanstack/react-query")) return "vendor-tanstack";
          if (id.includes("lucide-react")) return "vendor-icons";
          if (id.includes("zustand") || id.includes("date-fns")) return "vendor-utils";
          if (id.includes("@zxing/browser") || id.includes("@zxing/library")) return "vendor-qr";
        }
      }
    }
  },
  server: {
    host: "0.0.0.0",
    port: parseInt(process.env.PORT || "3003"),
    watch: { ignored: ["**/routeTree.gen.ts"] },
    proxy: {
      "/api": {
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
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvYXBwL2FwcHMvZXBpY2VyaWVcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfZmlsZW5hbWUgPSBcIi9hcHAvYXBwcy9lcGljZXJpZS92aXRlLmNvbmZpZy50c1wiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9pbXBvcnRfbWV0YV91cmwgPSBcImZpbGU6Ly8vYXBwL2FwcHMvZXBpY2VyaWUvdml0ZS5jb25maWcudHNcIjsvLy8gPHJlZmVyZW5jZSB0eXBlcz1cInZpdGVzdFwiIC8+XG5pbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tICd2aXRlJ1xuaW1wb3J0IHsgVGFuU3RhY2tSb3V0ZXJWaXRlIH0gZnJvbSAnQHRhbnN0YWNrL3JvdXRlci12aXRlLXBsdWdpbidcbmltcG9ydCByZWFjdCBmcm9tICdAdml0ZWpzL3BsdWdpbi1yZWFjdCdcbmltcG9ydCBwYXRoIGZyb20gJ3BhdGgnXG5cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XG4gIHBsdWdpbnM6IFtUYW5TdGFja1JvdXRlclZpdGUoKSwgcmVhY3QoKV0sXG4gIHJlc29sdmU6IHtcbiAgICBhbGlhczoge1xuICAgICAgJ0AnOiBwYXRoLnJlc29sdmUoX19kaXJuYW1lLCAnLi9zcmMnKSxcbiAgICAgICdAc2hhcmVkJzogcGF0aC5yZXNvbHZlKF9fZGlybmFtZSwgJy4uLy4uL3BhY2thZ2VzL3NoYXJlZC9zcmMnKSxcbiAgICB9LFxuICB9LFxuICBiYXNlOiAnL2VwaWNlcmllLycsXG4gIGJ1aWxkOiB7XG4gICAgY2h1bmtTaXplV2FybmluZ0xpbWl0OiA2MDAsXG4gICAgcm9sbHVwT3B0aW9uczoge1xuICAgICAgb3V0cHV0OiB7XG4gICAgICAgIG1hbnVhbENodW5rczogKGlkKSA9PiB7XG4gICAgICAgICAgaWYgKGlkLmluY2x1ZGVzKCdub2RlX21vZHVsZXMvcmVhY3QvJykgfHwgaWQuaW5jbHVkZXMoJ25vZGVfbW9kdWxlcy9yZWFjdC1kb20vJykpIHJldHVybiAndmVuZG9yLXJlYWN0J1xuICAgICAgICAgIGlmIChpZC5pbmNsdWRlcygnQHRhbnN0YWNrL3JlYWN0LXJvdXRlcicpIHx8IGlkLmluY2x1ZGVzKCdAdGFuc3RhY2svcmVhY3QtcXVlcnknKSkgcmV0dXJuICd2ZW5kb3ItdGFuc3RhY2snXG4gICAgICAgICAgaWYgKGlkLmluY2x1ZGVzKCdsdWNpZGUtcmVhY3QnKSkgcmV0dXJuICd2ZW5kb3ItaWNvbnMnXG4gICAgICAgICAgaWYgKGlkLmluY2x1ZGVzKCd6dXN0YW5kJykgfHwgaWQuaW5jbHVkZXMoJ2RhdGUtZm5zJykpIHJldHVybiAndmVuZG9yLXV0aWxzJ1xuICAgICAgICAgIGlmIChpZC5pbmNsdWRlcygnQHp4aW5nL2Jyb3dzZXInKSB8fCBpZC5pbmNsdWRlcygnQHp4aW5nL2xpYnJhcnknKSkgcmV0dXJuICd2ZW5kb3ItcXInXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIHNlcnZlcjoge1xuICAgIGhvc3Q6ICcwLjAuMC4wJyxcbiAgICBwb3J0OiBwYXJzZUludChwcm9jZXNzLmVudi5QT1JUIHx8ICczMDAzJyksXG4gICAgd2F0Y2g6IHsgaWdub3JlZDogWycqKi9yb3V0ZVRyZWUuZ2VuLnRzJ10gfSxcbiAgICBwcm94eToge1xuICAgICAgJy9hcGknOiB7XG4gICAgICAgIHRhcmdldDogcHJvY2Vzcy5lbnYuRE9DS0VSID09PSAndHJ1ZScgPyAnaHR0cDovL2FwaTo4MDAwJyA6ICdodHRwOi8vbG9jYWxob3N0OjgwMDEnLFxuICAgICAgICBjaGFuZ2VPcmlnaW46IHRydWUsXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIHRlc3Q6IHtcbiAgICBnbG9iYWxzOiB0cnVlLFxuICAgIGVudmlyb25tZW50OiAnanNkb20nLFxuICAgIHNldHVwRmlsZXM6ICcuL3NyYy90ZXN0L3NldHVwLnRzJyxcbiAgICBjc3M6IGZhbHNlLFxuICAgIGluY2x1ZGU6IFsnc3JjLyoqLyoue3Rlc3Qsc3BlY30ue3RzLHRzeH0nXSxcbiAgfSxcbn0pXG4iXSwKICAibWFwcGluZ3MiOiAiO0FBQ0EsU0FBUyxvQkFBb0I7QUFDN0IsU0FBUywwQkFBMEI7QUFDbkMsT0FBTyxXQUFXO0FBQ2xCLE9BQU8sVUFBVTtBQUpqQixJQUFNLG1DQUFtQztBQU16QyxJQUFPLHNCQUFRLGFBQWE7QUFBQSxFQUMxQixTQUFTLENBQUMsbUJBQW1CLEdBQUcsTUFBTSxDQUFDO0FBQUEsRUFDdkMsU0FBUztBQUFBLElBQ1AsT0FBTztBQUFBLE1BQ0wsS0FBSyxLQUFLLFFBQVEsa0NBQVcsT0FBTztBQUFBLE1BQ3BDLFdBQVcsS0FBSyxRQUFRLGtDQUFXLDJCQUEyQjtBQUFBLElBQ2hFO0FBQUEsRUFDRjtBQUFBLEVBQ0EsTUFBTTtBQUFBLEVBQ04sT0FBTztBQUFBLElBQ0wsdUJBQXVCO0FBQUEsSUFDdkIsZUFBZTtBQUFBLE1BQ2IsUUFBUTtBQUFBLFFBQ04sY0FBYyxDQUFDLE9BQU87QUFDcEIsY0FBSSxHQUFHLFNBQVMscUJBQXFCLEtBQUssR0FBRyxTQUFTLHlCQUF5QixFQUFHLFFBQU87QUFDekYsY0FBSSxHQUFHLFNBQVMsd0JBQXdCLEtBQUssR0FBRyxTQUFTLHVCQUF1QixFQUFHLFFBQU87QUFDMUYsY0FBSSxHQUFHLFNBQVMsY0FBYyxFQUFHLFFBQU87QUFDeEMsY0FBSSxHQUFHLFNBQVMsU0FBUyxLQUFLLEdBQUcsU0FBUyxVQUFVLEVBQUcsUUFBTztBQUM5RCxjQUFJLEdBQUcsU0FBUyxnQkFBZ0IsS0FBSyxHQUFHLFNBQVMsZ0JBQWdCLEVBQUcsUUFBTztBQUFBLFFBQzdFO0FBQUEsTUFDRjtBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQUEsRUFDQSxRQUFRO0FBQUEsSUFDTixNQUFNO0FBQUEsSUFDTixNQUFNLFNBQVMsUUFBUSxJQUFJLFFBQVEsTUFBTTtBQUFBLElBQ3pDLE9BQU8sRUFBRSxTQUFTLENBQUMscUJBQXFCLEVBQUU7QUFBQSxJQUMxQyxPQUFPO0FBQUEsTUFDTCxRQUFRO0FBQUEsUUFDTixRQUFRLFFBQVEsSUFBSSxXQUFXLFNBQVMsb0JBQW9CO0FBQUEsUUFDNUQsY0FBYztBQUFBLE1BQ2hCO0FBQUEsSUFDRjtBQUFBLEVBQ0Y7QUFBQSxFQUNBLE1BQU07QUFBQSxJQUNKLFNBQVM7QUFBQSxJQUNULGFBQWE7QUFBQSxJQUNiLFlBQVk7QUFBQSxJQUNaLEtBQUs7QUFBQSxJQUNMLFNBQVMsQ0FBQywrQkFBK0I7QUFBQSxFQUMzQztBQUNGLENBQUM7IiwKICAibmFtZXMiOiBbXQp9Cg==
