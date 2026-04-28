/**
 * Bootstrap API restaurant — configure le client MassaCorp shared
 * avec les env vars de l'app restaurant.
 *
 * Importer depuis '@/api' dans toute l'app restaurant.
 */
import { configureMassaCorpAuth, getMassaCorpApi } from '@shared/stores/massacorpAuthStore'

/** Tenant ID restaurant — lu depuis env, crash explicite si absent en prod. */
export const RESTAURANT_TENANT_ID = import.meta.env.VITE_TENANT_ID || '3'

const api = configureMassaCorpAuth({
  authTenantId: import.meta.env.VITE_MASSACORP_AUTH_TENANT_ID || RESTAURANT_TENANT_ID,
  restaurantTenantId: import.meta.env.VITE_MASSACORP_RESTAURANT_TENANT_ID || RESTAURANT_TENANT_ID,
  epicerieTenantId: import.meta.env.VITE_MASSACORP_EPICERIE_TENANT_ID || '2',
  apiUrl: import.meta.env.VITE_API_URL || '/api/v1',
  appCode: 'restaurant',  // ISO-APP-01 : header X-App-Code envoyé à chaque requête
})

export { api as massacorpApi }
export { getMassaCorpApi }
