import type { Brand } from './index'
import { marvelineBrand } from './marveline'
import { lesplendidBrand } from './lesplendid'

const BRANDS: Record<string, Brand> = {
  marveline: marvelineBrand,
  lesplendid: lesplendidBrand,
}

const code = (import.meta.env.VITE_BRAND as string | undefined) ?? 'marveline'

export const BRAND: Brand = BRANDS[code] ?? marvelineBrand

export function useBrand(): Brand {
  return BRAND
}

export function applyBrandCssVars(brand: Brand = BRAND): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.style.setProperty('--brand-primary-rgb', brand.colors.primaryRgb)
  for (const [shade, hex] of Object.entries(brand.colors.palette)) {
    const rgb = hexToRgb(hex)
    if (rgb) root.style.setProperty(`--brand-primary-${shade}-rgb`, rgb)
  }
  root.setAttribute('data-brand', brand.code)

  document.title = brand.name

  const themeMeta = document.querySelector('meta[name="theme-color"]')
  if (themeMeta) themeMeta.setAttribute('content', brand.colors.primary)

  const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (favicon) {
    favicon.setAttribute('href', brand.logoSquare)
    favicon.setAttribute('type', guessMime(brand.logoSquare))
  }

  const appleIcon = document.querySelector<HTMLLinkElement>('link[rel="apple-touch-icon"]')
  if (appleIcon) appleIcon.setAttribute('href', brand.logoSquare)
}

function guessMime(path: string): string {
  if (path.endsWith('.svg')) return 'image/svg+xml'
  if (path.endsWith('.png')) return 'image/png'
  if (path.endsWith('.ico')) return 'image/x-icon'
  if (path.endsWith('.webp')) return 'image/webp'
  return 'image/png'
}

function hexToRgb(hex: string): string | null {
  const match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex.trim())
  if (!match) return null
  const r = parseInt(match[1], 16)
  const g = parseInt(match[2], 16)
  const b = parseInt(match[3], 16)
  return r + ' ' + g + ' ' + b
}

/**
 * Refresh brand from backend `/tenant/brand` endpoint.
 *
 * Best-effort : si le backend est offline ou renvoie 404, on garde le brand
 * hardcode (BRAND). Si la reponse arrive, on merge les champs dynamiques
 * (palette, logo_url, contact_*) dans BRAND et on re-applique les CSS vars.
 *
 * Appele depuis main.tsx apres le applyBrandCssVars() initial.
 */
export async function refreshBrandFromApi(apiUrl = '/api/v1'): Promise<void> {
  if (typeof window === 'undefined') return
  try {
    const res = await fetch(`${apiUrl}/tenant/brand?brand_code=${encodeURIComponent(BRAND.code)}`, {
      headers: { 'Accept': 'application/json' },
    })
    if (!res.ok) return
    const data = await res.json()
    if (!data?.primary_color || !data?.palette) return

    // Merge into BRAND (mutate : seul endroit autorise)
    BRAND.name = data.display_name ?? BRAND.name
    BRAND.shortName = (data.display_name ?? BRAND.name).split(' ')[0] ?? BRAND.shortName
    BRAND.tagline = data.tagline ?? BRAND.tagline
    BRAND.colors.primary = data.primary_color
    BRAND.colors.primaryRgb = data.primary_rgb
    BRAND.colors.palette = data.palette as Record<string, string>
    if (data.logo_url) BRAND.logo = data.logo_url
    if (data.logo_square_url) BRAND.logoSquare = data.logo_square_url
    if (data.contact_email) BRAND.legal.email = data.contact_email
    if (data.contact_phone) BRAND.legal.phone = data.contact_phone

    applyBrandCssVars(BRAND)
    document.title = BRAND.name
  } catch {
    // silencieux : fallback hardcode reste en place
  }
}
