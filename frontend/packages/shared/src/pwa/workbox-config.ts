/**
 * Configuration Workbox partagée pour les 3 apps PWA.
 *
 * Stratégies :
 *   - StaleWhileRevalidate : listes produits, catalogue, stock, tables
 *   - NetworkFirst : commandes en cours, statuts temps réel
 *   - NetworkOnly + BackgroundSync : mutations (POST/PUT/DELETE)
 *
 * À utiliser avec vite-plugin-pwa dans chaque vite.config.ts :
 *   import { VitePWA } from 'vite-plugin-pwa'
 *   import { workboxConfig } from '@shared/pwa/workbox-config'
 */

import type { ManifestOptions } from 'vite-plugin-pwa'

export interface PwaAppConfig {
  appName: string
  shortName: string
  description: string
  themeColor: string
  backgroundColor: string
  scope: string
  startUrl: string
}

export function buildManifest(config: PwaAppConfig): Partial<ManifestOptions> {
  return {
    name: config.appName,
    short_name: config.shortName,
    description: config.description,
    theme_color: config.themeColor,
    background_color: config.backgroundColor,
    display: 'standalone',
    orientation: 'any',
    scope: config.scope,
    start_url: config.startUrl,
    icons: [
      { src: `${config.scope}icons/icon-192.png`, sizes: '192x192', type: 'image/png' },
      { src: `${config.scope}icons/icon-512.png`, sizes: '512x512', type: 'image/png' },
      { src: `${config.scope}icons/icon-maskable-512.png`, sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  }
}

/**
 * Options Workbox communes aux 3 apps.
 * Chaque app peut extend si besoin.
 */
export const workboxOptions = {
  runtimeCaching: [
    // Listes et catalogues — StaleWhileRevalidate (rapide, refresh en background)
    {
      urlPattern: /\/api\/v1\/(products|categories|bundles|customers|epicerie\/stock|restaurant\/tables|restaurant\/variantes-plat)/,
      handler: 'StaleWhileRevalidate' as const,
      options: {
        cacheName: 'api-lists',
        expiration: { maxEntries: 200, maxAgeSeconds: 3600 },
        cacheableResponse: { statuses: [0, 200] },
      },
    },
    // Commandes en cours — NetworkFirst (fraîcheur prioritaire)
    {
      urlPattern: /\/api\/v1\/(restaurant\/commandes|epicerie\/ventes)/,
      handler: 'NetworkFirst' as const,
      options: {
        cacheName: 'api-realtime',
        expiration: { maxEntries: 50, maxAgeSeconds: 300 },
        networkTimeoutSeconds: 3,
      },
    },
    // Dashboard / stats — StaleWhileRevalidate
    {
      urlPattern: /\/api\/v1\/(dashboard|epicerie\/dashboard|restaurant\/dashboard)/,
      handler: 'StaleWhileRevalidate' as const,
      options: {
        cacheName: 'api-dashboard',
        expiration: { maxEntries: 10, maxAgeSeconds: 600 },
      },
    },
    // Auth endpoints — NetworkOnly (jamais cacher)
    {
      urlPattern: /\/api\/v1\/auth/,
      handler: 'NetworkOnly' as const,
    },
  ],
}
