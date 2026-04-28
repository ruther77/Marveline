/**
 * Brand system — permet de basculer l'identité visuelle de l'app
 * entre plusieurs clients (Marveline, Le Splendid Events, etc.)
 *
 * Contrôlé par la variable d'environnement VITE_BRAND (marveline | lesplendid).
 * Par défaut : marveline (compat historique).
 */

export interface BrandColors {
  /** Couleur principale (Marveline rose / Splendid doré) */
  primary: string
  /** RGB décomposé pour CSS vars (ex: "217 64 168") */
  primaryRgb: string
  /** Palette Tailwind primary-{50..950} — injectée en CSS vars */
  palette: Record<string, string>
}

export interface BrandLegal {
  siret?: string
  address?: string
  email?: string
  phone?: string
}

export interface Brand {
  /** Code unique (utilisé aussi comme tenant app_code custom) */
  code: 'marveline' | 'lesplendid'
  /** Tenant id par défaut pour l'écran login (override via VITE_TENANT_ID) */
  defaultTenantId: number
  /** Nom affiché partout dans l'UI */
  name: string
  /** Version courte (barre de nav, favicon) */
  shortName: string
  /** Tagline */
  tagline: string
  /** Chemin vers logo principal (public/) */
  logo: string
  /** Chemin vers logo carré / icône */
  logoSquare: string
  /** Description pour meta + manifest */
  description: string
  /** Couleurs */
  colors: BrandColors
  /** Informations légales */
  legal: BrandLegal
}

export { useBrand } from './select'
export { marvelineBrand } from './marveline'
export { lesplendidBrand } from './lesplendid'
