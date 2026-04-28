// vite.config.ts
import { defineConfig } from "file:///app/node_modules/.pnpm/vite@5.4.21/node_modules/vite/dist/node/index.js";
import { TanStackRouterVite } from "file:///app/node_modules/.pnpm/@tanstack+router-vite-plugin@1.166.9_@tanstack+react-router@1.167.0_react-dom@18.3.1_re_5ca7d75fa607ff91698f097c7a27ea4d/node_modules/@tanstack/router-vite-plugin/dist/esm/index.js";
import react from "file:///app/node_modules/.pnpm/@vitejs+plugin-react@4.7.0_vite@5.4.21/node_modules/@vitejs/plugin-react/dist/index.js";
import path from "path";
var __vite_injected_original_dirname = "/app/apps/restaurant";
var vite_config_default = defineConfig({
  plugins: [TanStackRouterVite(), react()],
  resolve: {
    alias: {
      "@": path.resolve(__vite_injected_original_dirname, "./src"),
      "@shared": path.resolve(__vite_injected_original_dirname, "../../packages/shared/src")
    }
  },
  base: "/restaurant/",
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes("node_modules/react/") || id.includes("node_modules/react-dom/")) return "vendor-react";
          if (id.includes("@tanstack/react-router") || id.includes("@tanstack/react-query")) return "vendor-tanstack";
          if (id.includes("lucide-react")) return "vendor-icons";
          if (id.includes("zustand") || id.includes("date-fns")) return "vendor-utils";
        }
      }
    }
  },
  server: {
    host: "0.0.0.0",
    port: parseInt(process.env.PORT || "3004"),
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
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvYXBwL2FwcHMvcmVzdGF1cmFudFwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiL2FwcC9hcHBzL3Jlc3RhdXJhbnQvdml0ZS5jb25maWcudHNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL2FwcC9hcHBzL3Jlc3RhdXJhbnQvdml0ZS5jb25maWcudHNcIjsvLy8gPHJlZmVyZW5jZSB0eXBlcz1cInZpdGVzdFwiIC8+XG5pbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tICd2aXRlJ1xuaW1wb3J0IHsgVGFuU3RhY2tSb3V0ZXJWaXRlIH0gZnJvbSAnQHRhbnN0YWNrL3JvdXRlci12aXRlLXBsdWdpbidcbmltcG9ydCByZWFjdCBmcm9tICdAdml0ZWpzL3BsdWdpbi1yZWFjdCdcbmltcG9ydCBwYXRoIGZyb20gJ3BhdGgnXG5cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XG4gIHBsdWdpbnM6IFtUYW5TdGFja1JvdXRlclZpdGUoKSwgcmVhY3QoKV0sXG4gIHJlc29sdmU6IHtcbiAgICBhbGlhczoge1xuICAgICAgJ0AnOiBwYXRoLnJlc29sdmUoX19kaXJuYW1lLCAnLi9zcmMnKSxcbiAgICAgICdAc2hhcmVkJzogcGF0aC5yZXNvbHZlKF9fZGlybmFtZSwgJy4uLy4uL3BhY2thZ2VzL3NoYXJlZC9zcmMnKSxcbiAgICB9LFxuICB9LFxuICBiYXNlOiAnL3Jlc3RhdXJhbnQvJyxcbiAgYnVpbGQ6IHtcbiAgICBjaHVua1NpemVXYXJuaW5nTGltaXQ6IDYwMCxcbiAgICByb2xsdXBPcHRpb25zOiB7XG4gICAgICBvdXRwdXQ6IHtcbiAgICAgICAgbWFudWFsQ2h1bmtzOiAoaWQpID0+IHtcbiAgICAgICAgICBpZiAoaWQuaW5jbHVkZXMoJ25vZGVfbW9kdWxlcy9yZWFjdC8nKSB8fCBpZC5pbmNsdWRlcygnbm9kZV9tb2R1bGVzL3JlYWN0LWRvbS8nKSkgcmV0dXJuICd2ZW5kb3ItcmVhY3QnXG4gICAgICAgICAgaWYgKGlkLmluY2x1ZGVzKCdAdGFuc3RhY2svcmVhY3Qtcm91dGVyJykgfHwgaWQuaW5jbHVkZXMoJ0B0YW5zdGFjay9yZWFjdC1xdWVyeScpKSByZXR1cm4gJ3ZlbmRvci10YW5zdGFjaydcbiAgICAgICAgICBpZiAoaWQuaW5jbHVkZXMoJ2x1Y2lkZS1yZWFjdCcpKSByZXR1cm4gJ3ZlbmRvci1pY29ucydcbiAgICAgICAgICBpZiAoaWQuaW5jbHVkZXMoJ3p1c3RhbmQnKSB8fCBpZC5pbmNsdWRlcygnZGF0ZS1mbnMnKSkgcmV0dXJuICd2ZW5kb3ItdXRpbHMnXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIHNlcnZlcjoge1xuICAgIGhvc3Q6ICcwLjAuMC4wJyxcbiAgICBwb3J0OiBwYXJzZUludChwcm9jZXNzLmVudi5QT1JUIHx8ICczMDA0JyksXG4gICAgd2F0Y2g6IHsgaWdub3JlZDogWycqKi9yb3V0ZVRyZWUuZ2VuLnRzJ10gfSxcbiAgICBwcm94eToge1xuICAgICAgJy9hcGknOiB7XG4gICAgICAgIHRhcmdldDogcHJvY2Vzcy5lbnYuRE9DS0VSID09PSAndHJ1ZScgPyAnaHR0cDovL2FwaTo4MDAwJyA6ICdodHRwOi8vbG9jYWxob3N0OjgwMDEnLFxuICAgICAgICBjaGFuZ2VPcmlnaW46IHRydWUsXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIHRlc3Q6IHtcbiAgICBnbG9iYWxzOiB0cnVlLFxuICAgIGVudmlyb25tZW50OiAnanNkb20nLFxuICAgIHNldHVwRmlsZXM6ICcuL3NyYy90ZXN0L3NldHVwLnRzJyxcbiAgICBjc3M6IGZhbHNlLFxuICAgIGluY2x1ZGU6IFsnc3JjLyoqLyoue3Rlc3Qsc3BlY30ue3RzLHRzeH0nXSxcbiAgfSxcbn0pXG4iXSwKICAibWFwcGluZ3MiOiAiO0FBQ0EsU0FBUyxvQkFBb0I7QUFDN0IsU0FBUywwQkFBMEI7QUFDbkMsT0FBTyxXQUFXO0FBQ2xCLE9BQU8sVUFBVTtBQUpqQixJQUFNLG1DQUFtQztBQU16QyxJQUFPLHNCQUFRLGFBQWE7QUFBQSxFQUMxQixTQUFTLENBQUMsbUJBQW1CLEdBQUcsTUFBTSxDQUFDO0FBQUEsRUFDdkMsU0FBUztBQUFBLElBQ1AsT0FBTztBQUFBLE1BQ0wsS0FBSyxLQUFLLFFBQVEsa0NBQVcsT0FBTztBQUFBLE1BQ3BDLFdBQVcsS0FBSyxRQUFRLGtDQUFXLDJCQUEyQjtBQUFBLElBQ2hFO0FBQUEsRUFDRjtBQUFBLEVBQ0EsTUFBTTtBQUFBLEVBQ04sT0FBTztBQUFBLElBQ0wsdUJBQXVCO0FBQUEsSUFDdkIsZUFBZTtBQUFBLE1BQ2IsUUFBUTtBQUFBLFFBQ04sY0FBYyxDQUFDLE9BQU87QUFDcEIsY0FBSSxHQUFHLFNBQVMscUJBQXFCLEtBQUssR0FBRyxTQUFTLHlCQUF5QixFQUFHLFFBQU87QUFDekYsY0FBSSxHQUFHLFNBQVMsd0JBQXdCLEtBQUssR0FBRyxTQUFTLHVCQUF1QixFQUFHLFFBQU87QUFDMUYsY0FBSSxHQUFHLFNBQVMsY0FBYyxFQUFHLFFBQU87QUFDeEMsY0FBSSxHQUFHLFNBQVMsU0FBUyxLQUFLLEdBQUcsU0FBUyxVQUFVLEVBQUcsUUFBTztBQUFBLFFBQ2hFO0FBQUEsTUFDRjtBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQUEsRUFDQSxRQUFRO0FBQUEsSUFDTixNQUFNO0FBQUEsSUFDTixNQUFNLFNBQVMsUUFBUSxJQUFJLFFBQVEsTUFBTTtBQUFBLElBQ3pDLE9BQU8sRUFBRSxTQUFTLENBQUMscUJBQXFCLEVBQUU7QUFBQSxJQUMxQyxPQUFPO0FBQUEsTUFDTCxRQUFRO0FBQUEsUUFDTixRQUFRLFFBQVEsSUFBSSxXQUFXLFNBQVMsb0JBQW9CO0FBQUEsUUFDNUQsY0FBYztBQUFBLE1BQ2hCO0FBQUEsSUFDRjtBQUFBLEVBQ0Y7QUFBQSxFQUNBLE1BQU07QUFBQSxJQUNKLFNBQVM7QUFBQSxJQUNULGFBQWE7QUFBQSxJQUNiLFlBQVk7QUFBQSxJQUNaLEtBQUs7QUFBQSxJQUNMLFNBQVMsQ0FBQywrQkFBK0I7QUFBQSxFQUMzQztBQUNGLENBQUM7IiwKICAibmFtZXMiOiBbXQp9Cg==
