import type { Brand } from './index'

/**
 * Le Splendid Events — location événementielle Grand Est + Paris.
 *
 * Palette dorée/champagne #c9a961 (choix client).
 * Logo officiel : rouge bordeaux + bleu marine (www.le-splendid.events).
 */
export const lesplendidBrand: Brand = {
  code: 'lesplendid',
  defaultTenantId: 5,
  name: 'Le Splendid Events',
  shortName: 'Splendid',
  tagline: 'Location mariage & événementiel',
  logo: '/brands/lesplendid/logo.png',
  logoSquare: '/brands/lesplendid/logo.png',
  description: 'Le Splendid Events — location matériel et décoration pour mariages et événements',
  colors: {
    primary: '#c9a961',
    primaryRgb: '201 169 97',
    palette: {
      50:  '#fbf8ee',
      100: '#f6edd1',
      200: '#eedaa5',
      300: '#e3c274',
      400: '#d7ae54',
      500: '#c9a961',
      600: '#a8842e',
      700: '#876826',
      800: '#6d5423',
      900: '#5b4622',
      950: '#332511',
    },
  },
  legal: {
    email: 'contact@le-splendid.events',
  },
}
