/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans:    ['Manrope', 'system-ui', 'sans-serif'],
        display: ['Sora', 'system-ui', 'sans-serif'],
      },
      colors: {
        // --------------------------------------------------------
        // Palette "dark-*" — RESPONSIVE AU THÈME via RGB variables
        //   Light : dark-950=#f2f6fb (bg), dark-900=#fff (carte), dark-50=#16253d (texte)
        //   Dark  : dark-950=#07101f (bg), dark-900=#0d1e33 (carte), dark-50=#dde6f0 (texte)
        // Compatible opacité : bg-dark-900/80, border-dark-700/50, etc.
        // --------------------------------------------------------
        dark: {
          50:  'rgb(var(--c-text-rgb) / <alpha-value>)',   // texte principal
          100: 'rgb(var(--c-text2-rgb) / <alpha-value>)',  // texte secondaire
          200: 'rgb(var(--c-body2-rgb) / <alpha-value>)',  // corps léger
          300: 'rgb(var(--c-muted2-rgb) / <alpha-value>)', // muted2
          400: 'rgb(var(--c-muted2-rgb) / <alpha-value>)', // muted2 (alias)
          500: 'rgb(var(--c-muted-rgb) / <alpha-value>)',  // muted
          600: 'rgb(var(--c-border2-rgb) / <alpha-value>)',// border2
          700: 'rgb(var(--c-border-rgb) / <alpha-value>)', // border
          800: 'rgb(var(--c-s2-rgb) / <alpha-value>)',     // surface2
          900: 'rgb(var(--c-s1-rgb) / <alpha-value>)',     // surface (cartes)
          950: 'rgb(var(--c-bg-rgb) / <alpha-value>)',     // fond page
        },

        // --------------------------------------------------------
        // Couleurs sémantiques — alias CSS variables directes
        // Usage : bg-surface, text-body, border-border, etc.
        // --------------------------------------------------------
        bg:       'var(--bg)',
        surface:  'var(--s1)',
        surface2: 'var(--s2)',
        'layer-border':  'var(--border)',
        'layer-border2': 'var(--border2)',
        body:     'var(--text)',
        muted:    'var(--muted)',
        muted2:   'var(--muted2)',
        accent:   'var(--pink)',
        accent2:  'var(--pink2)',
        success:  'var(--green)',
        info:     'var(--blue)',
        warning:  'var(--orange)',
        danger:   'var(--red)',
        caution:  'var(--yellow)',
        subtle:   'var(--purple)',

        // --------------------------------------------------------
        // Palette primary — injectee au runtime via CSS vars (brand switch)
        // Voir src/brand/select.ts applyBrandCssVars()
        // --------------------------------------------------------
        primary: {
          50:  'rgb(var(--brand-primary-50-rgb) / <alpha-value>)',
          100: 'rgb(var(--brand-primary-100-rgb) / <alpha-value>)',
          200: 'rgb(var(--brand-primary-200-rgb) / <alpha-value>)',
          300: 'rgb(var(--brand-primary-300-rgb) / <alpha-value>)',
          400: 'rgb(var(--brand-primary-400-rgb) / <alpha-value>)',
          500: 'rgb(var(--brand-primary-500-rgb) / <alpha-value>)',
          600: 'rgb(var(--brand-primary-600-rgb) / <alpha-value>)',
          700: 'rgb(var(--brand-primary-700-rgb) / <alpha-value>)',
          800: 'rgb(var(--brand-primary-800-rgb) / <alpha-value>)',
          900: 'rgb(var(--brand-primary-900-rgb) / <alpha-value>)',
          950: 'rgb(var(--brand-primary-950-rgb) / <alpha-value>)',
        },

        // --------------------------------------------------------
        // Couleur d'accent secondaire "gold" — utilisée pour
        // les montants, mises en avant. Pas de brand switch ici :
        // on garde une teinte ambre stable sur tous les brands.
        // --------------------------------------------------------
        gold: {
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'fade-out': {
          '0%': { opacity: '1' },
          '100%': { opacity: '0' },
        },
        'zoom-in-95': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'zoom-out-95': {
          '0%': { opacity: '1', transform: 'scale(1)' },
          '100%': { opacity: '0', transform: 'scale(0.95)' },
        },
        'slide-in-from-right': {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        'slide-in-from-left': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        'slide-in-from-top': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(0)' },
        },
        'slide-in-from-bottom': {
          '0%': { transform: 'translateY(100%)' },
          '100%': { transform: 'translateY(0)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'stripes': {
          '0%': { backgroundPosition: '0 0' },
          '100%': { backgroundPosition: '40px 0' },
        },
        'spin': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.2s ease-out',
        'fade-out': 'fade-out 0.2s ease-out',
        'zoom-in-95': 'zoom-in-95 0.2s ease-out',
        'zoom-out-95': 'zoom-out-95 0.2s ease-out',
        'slide-in-from-right': 'slide-in-from-right 0.3s ease-out',
        'slide-in-from-left': 'slide-in-from-left 0.3s ease-out',
        'slide-in-from-top': 'slide-in-from-top 0.3s ease-out',
        'slide-in-from-bottom': 'slide-in-from-bottom 0.3s ease-out',
        'shimmer': 'shimmer 2s infinite linear',
        'stripes': 'stripes 1s infinite linear',
        'spin': 'spin 1s linear infinite',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
