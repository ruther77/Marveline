/**
 * Bootstrap API épicerie — configure le client MassaCorp shared
 * avec les env vars de l'app épicerie.
 *
 * Importer depuis '@/api' dans toute l'app épicerie.
 */
import { configureMassaCorpAuth, getMassaCorpApi } from '@shared/stores/massacorpAuthStore'

const api = configureMassaCorpAuth({
  authTenantId: import.meta.env.VITE_MASSACORP_AUTH_TENANT_ID || import.meta.env.VITE_TENANT_ID || '2',
  restaurantTenantId: import.meta.env.VITE_MASSACORP_RESTAURANT_TENANT_ID || '3',
  epicerieTenantId: import.meta.env.VITE_MASSACORP_EPICERIE_TENANT_ID || import.meta.env.VITE_TENANT_ID || '2',
  apiUrl: import.meta.env.VITE_API_URL || '/api/v1',
  appCode: 'epicerie',  // ISO-APP-01 : header X-App-Code envoyé à chaque requête
})

export { api as massacorpApi }
export { getMassaCorpApi }
